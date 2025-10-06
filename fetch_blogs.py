#!/usr/bin/env python3
"""Fetch all ELS WordPress blogs and generate static HTML pages."""

from __future__ import annotations

import argparse
import html
import json
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import requests
from bs4 import BeautifulSoup


@dataclass
class BlogPost:
    """Structured representation of a WordPress blog post."""

    title: str
    author: str
    date: str
    url: str
    filename: str
    category: str
    preview: str
    blocks: List[Dict[str, object]]
    is_poem: bool = False


class BlogFetcher:
    def __init__(
        self,
        base_url: str = "https://elsiitk.wordpress.com",
        start_page: int = 3,
        end_page: int = 19,
        delay: float = 0.75,
        update_index: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.start_page = start_page
        self.end_page = end_page
        self.delay = delay
        self.update_index = update_index

        self.output_dir = Path("blogs")
        self.images_dir = Path("images/blogs")
        self.blog_index_path = Path("blog.html")
        self.metadata_path = Path("blogs_metadata.json")
        self.cards_output_path = Path("blog_cards_to_add.html")

        self.output_dir.mkdir(exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "ELS-Blog-Scraper/1.0 (+https://elsiitk.wordpress.com)",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )

        self.existing_blogs = {f.stem for f in self.output_dir.glob("*.html")}

    # ------------------------------------------------------------------
    # Content extraction helpers
    # ------------------------------------------------------------------
    def _normalize_whitespace(self, text: str) -> str:
        return re.sub(r"\s+", " ", text.strip())

    def _text_with_breaks(self, node: BeautifulSoup) -> str:
        for br in node.find_all("br"):
            br.replace_with("\n")
        return node.get_text(" ", strip=True)

    def _convert_node(self, node: BeautifulSoup) -> List[Dict[str, object]]:
        blocks: List[Dict[str, object]] = []
        name = node.name.lower()

        if name in {"p", "span"}:
            text = self._normalize_whitespace(self._text_with_breaks(node))
            if text:
                blocks.append({"type": "paragraph", "content": text})

        elif name in {"h2", "h3", "h4"}:
            text = self._normalize_whitespace(self._text_with_breaks(node))
            if text:
                blocks.append({"type": "heading", "level": name, "content": text})

        elif name == "blockquote":
            text = self._normalize_whitespace(self._text_with_breaks(node))
            if text:
                blocks.append({"type": "quote", "content": text})

        elif name in {"ul", "ol"}:
            items: List[str] = []
            for li in node.find_all("li", recursive=False):
                li_text = self._normalize_whitespace(self._text_with_breaks(li))
                if li_text:
                    items.append(li_text)
            if items:
                blocks.append(
                    {
                        "type": "list",
                        "ordered": name == "ol",
                        "items": items,
                    }
                )

        elif name == "pre":
            code_text = node.get_text("\n", strip=True)
            if code_text:
                blocks.append({"type": "code", "content": code_text})

        return blocks

    def _extract_blocks(self, parent: BeautifulSoup) -> List[Dict[str, object]]:
        blocks: List[Dict[str, object]] = []
        for child in parent.children:
            if getattr(child, "name", None) is None:
                continue

            name = child.name.lower()
            
            # Skip "Share this:" section
            text_content = child.get_text(strip=True).lower()
            if "share this:" in text_content or "click to share" in text_content:
                continue
            
            if name in {"p", "span", "h2", "h3", "h4", "blockquote", "ul", "ol", "pre"}:
                blocks.extend(self._convert_node(child))
            elif name in {"div", "section", "figure", "article"}:
                blocks.extend(self._extract_blocks(child))

        return blocks

    def _escape(self, text: str) -> str:
        return html.escape(text, quote=False)

    def _preview(self, blocks: Iterable[Dict[str, object]], length: int = 220) -> str:
        snippets: List[str] = []
        for block in blocks:
            if block["type"] in {"paragraph", "heading", "quote"}:
                snippets.append(block["content"])
            elif block["type"] == "list":
                snippets.extend(block["items"])
            if sum(len(fragment) for fragment in snippets) >= length:
                break

        preview = " ".join(snippets)
        preview = self._normalize_whitespace(preview)
        if len(preview) > length:
            preview = preview[:length].rstrip() + "..."
        return preview

    def _determine_category(self, title: str, blocks: List[Dict[str, object]]) -> tuple[str, bool]:
        """Returns (category, is_poem) tuple."""
        title_lower = title.lower()
        
        # Check if it's a poem
        is_poem = "poem" in title_lower or "poetry" in title_lower
        
        # Count short lines (poems tend to have many short lines)
        if not is_poem and blocks:
            short_lines = sum(
                1 for b in blocks
                if b.get("type") == "paragraph" and len(b.get("content", "")) < 80
            )
            if short_lines > len(blocks) * 0.6 and len(blocks) > 5:
                is_poem = True
        
        # Determine category
        if is_poem:
            category = "Poetry"
        elif any(word in title_lower for word in ("review", "album", "movie", "book", "show")):
            category = "Review"
        else:
            category = "Article"
        
        return category, is_poem

    # ------------------------------------------------------------------
    # Network helpers
    # ------------------------------------------------------------------
    def fetch_page_links(self, page_num: int) -> List[Dict[str, str]]:
        url = f"{self.base_url}/?query-0-page={page_num}"
        print(f"Fetching page {page_num}: {url}")
        try:
            response = self.session.get(url, timeout=20)
            response.raise_for_status()
        except Exception as exc:  # pragma: no cover - network failure logging
            print(f"  ✗ Error fetching page {page_num}: {exc}")
            return []

        soup = BeautifulSoup(response.content, "html.parser")
        links: List[Dict[str, str]] = []
        
        # WordPress block theme uses li.wp-block-post instead of article
        for post in soup.find_all("li", class_="wp-block-post"):
            # Title is in h3, not h2
            title_elem = post.find("h3")
            anchor = title_elem.find("a") if title_elem else None
            if not anchor or not anchor.get("href"):
                continue

            raw_title = title_elem.get_text(strip=True)
            date_elem = post.find("time")
            date_text = date_elem.get_text(strip=True) if date_elem else "Unknown Date"

            links.append(
                {
                    "url": anchor["href"],
                    "title": raw_title,
                    "date": date_text,
                }
            )

        print(f"  ✓ Found {len(links)} links on page {page_num}")
        return links

    def fetch_blog_content(self, blog_info: Dict[str, str]) -> Optional[BlogPost]:
        title = blog_info["title"].strip()
        filename = self._slugify(title)
        if filename in self.existing_blogs:
            print(f"  ↷ Skipping existing blog: {title}")
            return None

        print(f"  Fetching post: {title}")
        try:
            response = self.session.get(blog_info["url"], timeout=25)
            response.raise_for_status()
        except Exception as exc:  # pragma: no cover - network failure logging
            print(f"    ✗ Error fetching blog: {exc}")
            return None

        soup = BeautifulSoup(response.content, "html.parser")

        author_elem = (
            soup.select_one(".byline .author")
            or soup.select_one("span.author")
            or soup.select_one("a[rel='author']")
        )
        author = author_elem.get_text(strip=True) if author_elem else "Unknown"

        date_elem = soup.find("time", class_="entry-date")
        formatted_date = blog_info["date"]
        if date_elem:
            raw_date = date_elem.get("datetime") or date_elem.get_text(strip=True)
            formatted_date = self._format_date(raw_date) or formatted_date

        content_div = soup.find("div", class_="entry-content")
        if not content_div:
            print("    ✗ Could not find entry-content div")
            return None

        blocks = self._extract_blocks(content_div)
        if not blocks:
            text = self._normalize_whitespace(content_div.get_text(" ", strip=True))
            if text:
                blocks = [{"type": "paragraph", "content": text}]

        preview = self._preview(blocks)
        category, is_poem = self._determine_category(title, blocks)

        return BlogPost(
            title=title,
            author=author,
            date=formatted_date,
            url=blog_info["url"],
            filename=filename,
            category=category,
            preview=preview,
            blocks=blocks,
            is_poem=is_poem,
        )

    # ------------------------------------------------------------------
    # Output helpers
    # ------------------------------------------------------------------
    def _slugify(self, title: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9\-\s]", "", title)
        slug = re.sub(r"[\s\-]+", "_", slug.strip())
        return slug[:120]

    def _format_date(self, raw: str) -> Optional[str]:
        if not raw:
            return None
        raw = raw.strip()
        try:
            date_obj = datetime.fromisoformat(raw.replace("Z", ""))
        except ValueError:
            try:
                date_obj = datetime.strptime(raw.split("T")[0], "%Y-%m-%d")
            except ValueError:
                return None
        return date_obj.strftime("%B %d, %Y")

    def _block_to_html(self, block: Dict[str, object]) -> str:
        block_type = block["type"]
        if block_type == "paragraph":
            return (
                "      <p>\n        "
                + self._escape(block["content"])
                + "\n      </p>"
            )

        if block_type == "heading":
            level = block.get("level", "h3")
            level = level if level in {"h2", "h3", "h4"} else "h3"
            return (
                f"      <{level} class=\"text-2xl font-semibold text-gray-800\">"
                + self._escape(block["content"])
                + f"</{level}>"
            )

        if block_type == "quote":
            return (
                "      <blockquote class=\"border-l-4 border-gray-300 pl-4 italic text-gray-700\">\n        "
                + self._escape(block["content"])
                + "\n      </blockquote>"
            )

        if block_type == "list":
            ordered = bool(block.get("ordered"))
            tag = "ol" if ordered else "ul"
            classes = "list-decimal" if ordered else "list-disc"
            items_html = "\n".join(
                f"        <li>{self._escape(item)}</li>" for item in block.get("items", [])
            )
            return (
                f"      <{tag} class=\"{classes} pl-6 space-y-2 text-gray-800\">\n"
                + items_html
                + f"\n      </{tag}>"
            )

        if block_type == "code":
            return (
                "      <pre class=\"bg-gray-900 text-gray-100 text-sm rounded-lg p-4 overflow-auto whitespace-pre-wrap\">\n"
                + html.escape(str(block.get("content", "")))
                + "\n      </pre>"
            )

        return ""

    def _blocks_to_html(self, blocks: List[Dict[str, object]], is_poem: bool = False) -> str:
        if is_poem:
            return self._poem_to_html(blocks)
        
        rendered = [self._block_to_html(block) for block in blocks if block]
        rendered = [block for block in rendered if block]
        return "\n\n      <br>\n\n".join(rendered)
    
    def _poem_to_html(self, blocks: List[Dict[str, object]]) -> str:
        """Format poem with line-by-line animation like existing poems."""
        lines: List[str] = []
        delay = 0
        
        for block in blocks:
            if block.get("type") == "paragraph":
                content = self._escape(block.get("content", ""))
                if content:
                    lines.append(f'          <p data-aos="fade-up" data-aos-delay="{delay}">{content}</p>')
                    delay += 50
            elif block.get("type") == "heading":
                content = self._escape(block.get("content", ""))
                if content:
                    lines.append(f'          <br><p data-aos="fade-up" data-aos-delay="{delay}" class="font-bold">{content}</p>')
                    delay += 50
        
        return "\n".join(lines)

    def generate_html(self, post: BlogPost) -> str:
        hero_image = f"../images/blogs/{post.filename}.png"
        content_html = self._blocks_to_html(post.blocks, post.is_poem)
        
        # Different styling for poems vs articles
        if post.is_poem:
            content_wrapper = f'''    <main class="max-w-3xl mx-auto px-4 py-20">
      <div class="text-center text-xl md:text-2xl leading-[2.5rem] text-gray-800 space-y-6">
        <!-- Poem lines with scroll animation -->
        <div class="space-y-6">
          <!-- Each line wrapped with AOS fade-up -->
{content_html}
          </div>
      </div>

      <div class="mt-16 text-center">
        <a href="../blog.html" class="inline-block text-blue-600 hover:underline font-medium text-sm">
          ← Back to all blog posts
        </a>
      </div>
    </main>'''
        else:
            content_wrapper = f'''  <main class="max-w-3xl mx-auto px-4 py-16" data-aos="fade-up">
    <div class="prose max-w-none text-lg leading-relaxed text-gray-800 prose-p:mb-4">
{content_html}
    </div>

    <div class="mt-12 text-center">
      <a href="../blog.html" class="inline-block text-blue-600 hover:underline font-medium text-sm">
        ← Back to all blog posts
      </a>
    </div>
  </main>'''

        return f"""<!DOCTYPE html>
<html lang=\"en\" class=\"scroll-smooth\">

<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{self._escape(post.title)} | ELS IIT Kanpur</title>
  <link rel=\"icon\" href=\"../images/logo-bg.png\" type=\"image/png\" />

  <!-- Fonts & Tailwind -->
  <link href=\"https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&display=swap\" rel=\"stylesheet\" />
  <script src=\"https://cdn.tailwindcss.com\"></script>

  <!-- AOS for animations -->
  <link href=\"https://unpkg.com/aos@2.3.1/dist/aos.css\" rel=\"stylesheet\" />
  <script src=\"https://unpkg.com/aos@2.3.1/dist/aos.js\"></script>

  <style>
    body {{
      font-family: 'Playfair Display', serif;
      background-color: #fef9f4;
      background-image: url('../paper-texture-wide.png');
      background-repeat: repeat-x;
      background-position: top center;
      background-attachment: fixed;
      background-size: auto;
      color: #111;
    }}
  </style>
</head>

<body>
  <!-- Navigation Header -->
  <header class=\"sticky top-0 z-50 bg-[#fef9f4]/90 backdrop-blur-md border-b border-gray-200\">
    <div class=\"max-w-screen-xl mx-auto px-6 py-4 flex items-center justify-between\">
      <div class=\"flex items-center space-x-3\">
        <a href=\"../index.html\">
          <img src=\"../images/logo.png\" alt=\"ELS Logo\" class=\"h-12 w-auto sm:h-16\" />
        </a>
        <h2 class=\"text-base sm:text-lg md:text-2xl font-bold tracking-wide\">
          English Literary Society IIT Kanpur
        </h2>
      </div>

      <nav class=\"hidden md:flex space-x-6 text-sm md:text-base font-light uppercase tracking-widest\">
        <a href=\"../index.html\" class=\"hover:text-gray-700\">Home</a>
        <a href=\"../about.html\" class=\"hover:text-gray-700\">About</a>
        <a href=\"../events.html\" class=\"hover:text-gray-700\">Events</a>
        <a href=\"../blog.html\" class=\"hover:text-gray-700\">Blog</a>
        <a href=\"../Dandelion.html\" class=\"hover:text-gray-700\">Dandelion</a>
      </nav>

      <button id=\"menu-toggle\" class=\"md:hidden focus:outline-none\">
        <svg class=\"w-6 h-6\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" viewBox=\"0 0 24 24\"
          xmlns=\"http://www.w3.org/2000/svg\">
          <path stroke-linecap=\"round\" stroke-linejoin=\"round\" d=\"M4 6h16M4 12h16M4 18h16\"></path>
        </svg>
      </button>
    </div>

    <nav id=\"mobile-menu\"
      class=\"max-h-0 overflow-hidden transition-all duration-500 ease-in-out md:hidden flex flex-col text-sm font-light uppercase tracking-widest bg-[#fef9f4] px-6 shadow-md\">
      <a href=\"../index.html\" class=\"py-3 border-t hover:text-gray-700\">Home</a>
      <a href=\"../about.html\" class=\"py-3 border-t hover:text-gray-700\">About</a>
      <a href=\"../events.html\" class=\"py-3 border-t hover:text-gray-700\">Events</a>
      <a href=\"../blog.html\" class=\"py-3 border-t hover:text-gray-700\">Blog</a>
      <a href=\"../Dandelion.html\" class=\"py-3 border-y hover:text-gray-700\">Dandelion</a>
    </nav>
  </header>

  <script>
    const toggleBtn = document.getElementById('menu-toggle');
    const mobileMenu = document.getElementById('mobile-menu');

    let isOpen = false;
    toggleBtn.addEventListener('click', () => {{
      isOpen = !isOpen;
      mobileMenu.style.maxHeight = isOpen ? mobileMenu.scrollHeight + "px" : "0px";
    }});

    mobileMenu.querySelectorAll('a').forEach(link => {{
      link.addEventListener('click', () => {{
        isOpen = false;
        mobileMenu.style.maxHeight = "0px";
      }});
    }});
  </script>

  <section class=\"relative h-[90vh] flex items-center justify-center overflow-hidden\" data-aos=\"fade-up\">
    <div class=\"absolute inset-0 z-0\">
      <img src=\"{hero_image}\" alt=\"Blurred background\"
        class=\"w-full h-full object-cover blur-2xl scale-125 opacity-60\" />
      <div class=\"absolute inset-0 bg-gradient-to-b from-[#fef9f4]/90 to-[#fef9f4]/80\"></div>
    </div>

    <div class=\"relative z-10 flex flex-col items-center px-4\">
      <img src=\"{hero_image}\" alt=\"{self._escape(post.title)}\"
        class=\"max-h-[70vh] w-auto object-contain mb-6 rounded-xl shadow-2xl transition-all duration-1000 ease-in-out animate-fade-in-up\" />

      <div class=\"text-center text-black\" data-aos=\"fade-up\" data-aos-delay=\"200\">
        <h1 class=\"text-4xl md:text-5xl font-bold mb-2\">{self._escape(post.title)}</h1>
        <p class=\"text-sm md:text-base text-gray-700\">{self._escape(post.author)} | {self._escape(post.date)}</p>
      </div>
    </div>

    <div class=\"absolute bottom-4 left-1/2 transform -translate-x-1/2 z-20\">
      <div class=\"animate-bounce text-gray-500 text-xs\">Scroll Down ↓</div>
    </div>
  </section>

{content_wrapper}

  <script>
    AOS.init({{
      duration: 800,
      easing: 'ease-in-out',
      once: true,
    }});
  </script>
</body>

</html>
"""

    def save_blog(self, post: BlogPost) -> Optional[BlogPost]:
        filepath = self.output_dir / f"{post.filename}.html"
        try:
            filepath.write_text(self.generate_html(post), encoding="utf-8")
            self.existing_blogs.add(post.filename)
            print(f"    ✓ Created {filepath}")
            return post
        except Exception as exc:  # pragma: no cover - filesystem failure logging
            print(f"    ✗ Failed to write {filepath}: {exc}")
            return None

    def _card_html(self, post: BlogPost) -> str:
        return f"""      <!-- {self._escape(post.title)} -->
      <div
        class=\"group relative overflow-hidden rounded-lg shadow-md bg-white hover:shadow-xl transition-all duration-300\"
        data-category=\"{post.category}\">
        <a href=\"blogs/{post.filename}.html\">
          <img src=\"images/blogs/{post.filename}.png\" alt=\"{self._escape(post.title)}\"
            class=\"blog-img group-hover:opacity-70 transition\" />
          <div
            class=\"absolute inset-0 flex flex-col justify-end bg-gradient-to-t from-black/60 to-transparent opacity-0 group-hover:opacity-100 transition p-4 text-white\">
            <h3 class=\"text-2xl font-bold\">{self._escape(post.title)}\n            </h3>
            <p class=\"text-base mt-1 font-medium\">by {self._escape(post.author)} · {self._escape(post.date)}\n            </p>
            <p class=\"text-sm mt-2\">{self._escape(post.preview)}\n            </p>
          </div>
        </a>
      </div>"""

    def update_blog_index(self, posts: List[BlogPost]) -> None:
        if not self.blog_index_path.exists():
            print("⚠️ blog.html not found; skipping automatic index update.")
            return

        existing_html = self.blog_index_path.read_text(encoding="utf-8")
        insertion_point = existing_html.rfind("</section>")
        if insertion_point == -1:
            print("⚠️ Could not locate </section> in blog.html; skipping update.")
            return

        new_cards: List[str] = []
        already_present = existing_html.lower()
        for post in posts:
            marker = f"blogs/{post.filename}.html".lower()
            if marker in already_present:
                continue
            new_cards.append(self._card_html(post))

        if not new_cards:
            print("No new cards to append to blog.html")
            return

        insertion = "\n".join(new_cards) + "\n\n"
        updated_html = (
            existing_html[:insertion_point]
            + insertion
            + existing_html[insertion_point:]
        )
        self.blog_index_path.write_text(updated_html, encoding="utf-8")
        print(f"✓ Updated blog.html with {len(new_cards)} new cards")

        self.cards_output_path.write_text("\n".join(new_cards), encoding="utf-8")
        print(f"✓ Saved new card snippets to {self.cards_output_path}")

    def write_metadata(self, posts: List[BlogPost]) -> None:
        metadata = [asdict(post) for post in posts]
        self.metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        print(f"✓ Metadata written to {self.metadata_path}")

    def run(self) -> List[BlogPost]:
        collected_posts: List[BlogPost] = []
        print("=" * 70)
        print(f"Collecting blogs from pages {self.start_page} to {self.end_page}")
        print("=" * 70)

        all_links: List[Dict[str, str]] = []
        for page in range(self.start_page, self.end_page + 1):
            all_links.extend(self.fetch_page_links(page))
            time.sleep(self.delay)

        print(f"\nTotal candidate blogs: {len(all_links)}")
        print("=" * 70)

        for index, blog_info in enumerate(all_links, start=1):
            print(f"\n[{index}/{len(all_links)}]")
            post = self.fetch_blog_content(blog_info)
            if not post:
                continue

            saved = self.save_blog(post)
            if saved:
                collected_posts.append(saved)
            time.sleep(self.delay)

        if collected_posts:
            self.write_metadata(collected_posts)
            if self.update_index:
                self.update_blog_index(collected_posts)
        else:
            print("No new blogs were created; metadata and index not updated.")

        print("=" * 70)
        print(f"Completed. Created {len(collected_posts)} new blog files.")
        print("=" * 70)
        return collected_posts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch ELS WordPress blogs")
    parser.add_argument("--start", type=int, default=3, help="WordPress page to start from (inclusive)")
    parser.add_argument("--end", type=int, default=19, help="WordPress page to end at (inclusive)")
    parser.add_argument("--delay", type=float, default=0.75, help="Delay between requests in seconds")
    parser.add_argument(
        "--no-index",
        action="store_true",
        help="Do not update blog.html automatically",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    fetcher = BlogFetcher(
        start_page=args.start,
        end_page=args.end,
        delay=max(0.1, args.delay),
        update_index=not args.no_index,
    )
    fetcher.run()


if __name__ == "__main__":
    main()
