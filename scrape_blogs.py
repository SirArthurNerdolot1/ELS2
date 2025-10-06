#!/usr/bin/env python3
"""
WordPress Blog Scraper for ELS IIT Kanpur
Scrapes blogs from elsiitk.wordpress.com pages 3-19 and generates HTML files
"""

import requests
from bs4 import BeautifulSoup
import re
import time
import json
from pathlib import Path
from datetime import datetime

# Configuration
BASE_URL = "https://elsiitk.wordpress.com"
START_PAGE = 3
END_PAGE = 19
OUTPUT_DIR = Path("blogs")
IMAGES_DIR = Path("images/blogs")
DELAY_BETWEEN_REQUESTS = 1  # seconds

# Ensure directories exist
OUTPUT_DIR.mkdir(exist_ok=True)
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

def sanitize_filename(title):
    """Convert blog title to safe filename"""
    # Remove special characters and replace spaces with underscores
    filename = re.sub(r'[^\w\s-]', '', title)
    filename = re.sub(r'[-\s]+', '_', filename)
    return filename.strip('_')

def fetch_page_blogs(page_num):
    """Fetch all blog links from a WordPress page"""
    url = f"{BASE_URL}/?query-0-page={page_num}"
    print(f"\n📄 Fetching page {page_num}: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all blog post links
        blog_links = []
        articles = soup.find_all('article', class_='post')
        
        for article in articles:
            title_elem = article.find('h2', class_='entry-title')
            if title_elem:
                link = title_elem.find('a')
                if link and link.get('href'):
                    title = title_elem.get_text(strip=True)
                    blog_links.append({
                        'title': title,
                        'url': link['href']
                    })
        
        print(f"   ✓ Found {len(blog_links)} blogs on page {page_num}")
        return blog_links
    
    except Exception as e:
        print(f"   ✗ Error fetching page {page_num}: {e}")
        return []

def fetch_blog_content(blog_url):
    """Fetch full content of a single blog post"""
    try:
        response = requests.get(blog_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract title
        title_elem = soup.find('h1', class_='entry-title')
        title = title_elem.get_text(strip=True) if title_elem else "Untitled"
        
        # Extract author
        author_elem = soup.find('span', class_='author')
        author = author_elem.get_text(strip=True) if author_elem else "Unknown"
        
        # Extract date
        date_elem = soup.find('time', class_='entry-date')
        date = date_elem.get_text(strip=True) if date_elem else ""
        
        # Extract content
        content_elem = soup.find('div', class_='entry-content')
        if not content_elem:
            return None
        
        # Get all paragraphs
        paragraphs = []
        for elem in content_elem.find_all(['p', 'h2', 'h3', 'blockquote']):
            text = elem.get_text(strip=True)
            if text:
                if elem.name in ['h2', 'h3']:
                    paragraphs.append(f"<h3>{text}</h3>")
                elif elem.name == 'blockquote':
                    paragraphs.append(f'<p style="font-style: italic; margin: 2rem 0;">{text}</p>')
                else:
                    paragraphs.append(text)
        
        return {
            'title': title,
            'author': author,
            'date': date,
            'paragraphs': paragraphs,
            'url': blog_url
        }
    
    except Exception as e:
        print(f"   ✗ Error fetching blog content: {e}")
        return None

def generate_html(blog_data, filename):
    """Generate HTML file for a blog post"""
    
    # Determine category based on title
    title_lower = blog_data['title'].lower()
    if any(word in title_lower for word in ['review', 'album', 'movie', 'book', 'show']):
        category = 'Review'
    elif any(word in title_lower for word in ['poem', 'poetry']):
        category = 'Poem'
    else:
        category = 'Article'
    
    # Format paragraphs with <br> tags
    formatted_paragraphs = []
    for para in blog_data['paragraphs']:
        if para.startswith('<h3>') or para.startswith('<p style='):
            formatted_paragraphs.append(f"      {para}")
        else:
            formatted_paragraphs.append(f"      <p>\n        {para}\n      </p>")
        formatted_paragraphs.append("      <br>")
    
    # Remove last <br>
    if formatted_paragraphs and formatted_paragraphs[-1] == "      <br>":
        formatted_paragraphs.pop()
    
    content_html = "\n".join(formatted_paragraphs)
    
    # Generate image filename
    image_filename = f"{filename}.png"
    
    html_template = f"""<!DOCTYPE html>
<html lang="en" class="scroll-smooth">

<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{blog_data['title']} | ELS IIT Kanpur</title>
  <link rel="icon" href="../images/logo-bg.png" type="image/png" />

  <!-- Fonts & Tailwind -->
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&display=swap" rel="stylesheet" />
  <script src="https://cdn.tailwindcss.com"></script>

  <!-- AOS for animations -->
  <link href="https://unpkg.com/aos@2.3.1/dist/aos.css" rel="stylesheet" />
  <script src="https://unpkg.com/aos@2.3.1/dist/aos.js"></script>

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

    .hero-overlay {{
      background: linear-gradient(to bottom, rgba(0, 0, 0, 0.4), rgba(0, 0, 0, 0.75));
    }}
  </style>
</head>

<body>
  <!-- Navigation Header -->
  <header class="sticky top-0 z-50 bg-[#fef9f4]/90 backdrop-blur-md border-b border-gray-200">
    <div class="max-w-screen-xl mx-auto px-6 py-4 flex items-center justify-between">
      <!-- Logo + Title -->
      <div class="flex items-center space-x-3">
        <a href="../index.html">
          <img src="../images/logo.png" alt="ELS Logo" class="h-12 w-auto sm:h-16" />
        </a>
        <h2 id="navbar-title" class="text-base sm:text-lg md:text-2xl font-bold tracking-wide text-left md:text-left">
          English Literary Society IIT Kanpur
        </h2>

      </div>

      <!-- Desktop Nav -->
      <nav class="hidden md:flex space-x-6 text-sm md:text-base font-light uppercase tracking-widest">
        <a href="../index.html" class="hover:text-gray-700">Home</a>
        <a href="../about.html" class="hover:text-gray-700">About</a>
        <a href="../events.html" class="hover:text-gray-700">Events</a>
        <a href="../blog.html" class="hover:text-gray-700">Blog</a>
        <a href="../Dandelion.html" class="hover:text-gray-700">Dandelion</a>
      </nav>

      <!-- Hamburger Button (Mobile) -->
      <button id="menu-toggle" class="md:hidden focus:outline-none">
        <svg class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16"></path>
        </svg>
      </button>
    </div>

    <!-- Slide-Down Mobile Nav -->
    <nav id="mobile-menu"
      class="max-h-0 overflow-hidden transition-all duration-500 ease-in-out md:hidden flex flex-col text-sm font-light uppercase tracking-widest bg-[#fef9f4] px-6 shadow-md">
      <a href="../index.html" class="py-3 border-t hover:text-gray-700">Home</a>
      <a href="../about.html" class="py-3 border-t hover:text-gray-700">About</a>
      <a href="../events.html" class="py-3 border-t hover:text-gray-700">Events</a>
      <a href="../blog.html" class="py-3 border-t hover:text-gray-700">Blog</a>
      <a href="../Dandelion.html" class="py-3 border-y hover:text-gray-700">Dandelion</a>
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

  <!-- Hero Section with animations, blurred background, and image shadow -->
  <section class="relative h-[90vh] flex items-center justify-center overflow-hidden" data-aos="fade-up">
    <!-- Blurred Background -->
    <div class="absolute inset-0 z-0">
      <img src="../images/blogs/{image_filename}" alt="Blurred Background"
        class="w-full h-full object-cover blur-2xl scale-125 opacity-60" />
      <div class="absolute inset-0 bg-gradient-to-b from-[#fef9f4]/90 to-[#fef9f4]/80"></div>
    </div>

    <!-- Foreground Image and Text -->
    <div class="relative z-10 flex flex-col items-center justifyF-center px-4">
      <!-- Animated Image -->
      <img src="../images/blogs/{image_filename}" alt="{blog_data['title']}"
        class="max-h-[70vh] w-auto object-contain mb-6 rounded-xl shadow-2xl transition-all duration-1000 ease-in-out animate-fade-in-up" />

      <!-- Animated Text -->
      <div class="text-center text-black" data-aos="fade-up" data-aos-delay="200">
        <h1 class="text-4xl md:text-5xl font-bold mb-2">{blog_data['title']}</h1>
        <p class="text-sm md:text-base text-gray-700">{blog_data['author']} | {blog_data['date']}</p>
      </div>
    </div>

    <!-- Optional Scroll Down Indicator -->
    <div class="absolute bottom-4 left-1/2 transform -translate-x-1/2 z-20">
      <div class="animate-bounce text-gray-500 text-xs">Scroll Down ↓</div>
    </div>
  </section>



  <!-- Blog Body -->
  <main class="max-w-3xl mx-auto px-4 py-16" data-aos="fade-up">
    <div class="prose max-w-none text-lg leading-relaxed text-gray-800 prose-p:mb-4">
{content_html}
    </div>

    <!-- Back Button -->
    <div class="mt-12 text-center">
      <a href="../blog.html" class="inline-block text-blue-600 hover:underline font-medium text-sm">
        ← Back to all blog posts
      </a>
    </div>
  </main>

  <!-- AOS Init -->
  <script>
    AOS.init();
  </script>
</body>

</html>
"""
    
    return html_template, category

def create_blog_card_html(blog_data, filename, category):
    """Generate HTML for blog card in blog.html"""
    
    # Create short description (first 150 chars of first paragraph)
    description = ""
    if blog_data['paragraphs']:
        first_para = blog_data['paragraphs'][0]
        if not first_para.startswith('<'):
            description = first_para[:150] + "..." if len(first_para) > 150 else first_para
    
    image_filename = f"{filename}.png"
    
    card_html = f'''      <!-- {blog_data['title']} -->
      <div
        class="group relative overflow-hidden rounded-lg shadow-md bg-white hover:shadow-xl transition-all duration-300"
        data-category="{category}">
        <a href="blogs/{filename}.html">
          <img src="images/blogs/{image_filename}" alt="{blog_data['title']}"
            class="blog-img group-hover:opacity-70 transition" />
          <div
            class="absolute inset-0 flex flex-col justify-end bg-gradient-to-t from-black/60 to-transparent opacity-0 group-hover:opacity-100 transition p-4 text-white">
            <h3 class="text-2xl font-bold">{blog_data['title']}</h3>
            <p class="text-base mt-1 font-medium">by {blog_data['author']} · {blog_data['date']}</p>
            <p class="text-sm mt-2">{description}</p>
          </div>
        </a>
      </div>'''
    
    return card_html

def main():
    """Main scraping function"""
    print("🚀 Starting WordPress blog scraper...")
    print(f"📊 Scraping pages {START_PAGE} to {END_PAGE}")
    print(f"📁 Output directory: {OUTPUT_DIR}")
    
    all_blogs = []
    
    # Step 1: Fetch all blog links from all pages
    print("\n" + "="*60)
    print("STEP 1: Fetching blog links from all pages")
    print("="*60)
    
    for page_num in range(START_PAGE, END_PAGE + 1):
        blogs = fetch_page_blogs(page_num)
        all_blogs.extend(blogs)
        time.sleep(DELAY_BETWEEN_REQUESTS)
    
    print(f"\n✅ Total blogs found: {len(all_blogs)}")
    
    # Step 2: Fetch content for each blog and generate HTML
    print("\n" + "="*60)
    print("STEP 2: Fetching content and generating HTML files")
    print("="*60)
    
    successful_blogs = []
    blog_cards = []
    
    for i, blog in enumerate(all_blogs, 1):
        print(f"\n[{i}/{len(all_blogs)}] Processing: {blog['title']}")
        
        # Fetch blog content
        blog_data = fetch_blog_content(blog['url'])
        
        if not blog_data:
            print(f"   ⚠️  Skipping - couldn't fetch content")
            continue
        
        # Generate filename
        filename = sanitize_filename(blog_data['title'])
        filepath = OUTPUT_DIR / f"{filename}.html"
        
        # Check if file already exists
        if filepath.exists():
            print(f"   ⏭️  Skipping - file already exists")
            continue
        
        # Generate HTML
        html_content, category = generate_html(blog_data, filename)
        
        # Write HTML file
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"   ✅ Created: {filename}.html")
            
            # Store blog card data
            card_html = create_blog_card_html(blog_data, filename, category)
            blog_cards.append(card_html)
            
            successful_blogs.append({
                'title': blog_data['title'],
                'author': blog_data['author'],
                'date': blog_data['date'],
                'filename': filename,
                'category': category,
                'url': blog['url']
            })
            
        except Exception as e:
            print(f"   ✗ Error writing file: {e}")
        
        # Be polite to the server
        time.sleep(DELAY_BETWEEN_REQUESTS)
    
    # Step 3: Save metadata
    print("\n" + "="*60)
    print("STEP 3: Saving metadata")
    print("="*60)
    
    metadata_file = Path("scraped_blogs_metadata.json")
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(successful_blogs, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved metadata to {metadata_file}")
    
    # Step 4: Save blog cards HTML
    cards_file = Path("blog_cards.html")
    with open(cards_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(blog_cards))
    print(f"✅ Saved blog cards HTML to {cards_file}")
    
    # Summary
    print("\n" + "="*60)
    print("🎉 SCRAPING COMPLETE!")
    print("="*60)
    print(f"✅ Successfully created: {len(successful_blogs)} blog HTML files")
    print(f"📝 Metadata saved to: {metadata_file}")
    print(f"🎨 Blog cards HTML saved to: {cards_file}")
    print(f"\n⚠️  NOTE: You'll need to create placeholder images for:")
    print(f"   {IMAGES_DIR}/<filename>.png for each blog")
    print("\n📋 Next step: Copy contents of blog_cards.html into blog.html")

if __name__ == "__main__":
    main()
