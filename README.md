# ELS IIT Kanpur Website - React Version

English Literary Society IIT Kanpur official website built with React, TypeScript, and Tailwind CSS.

## Tech Stack

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool with Rolldown (experimental)
- **Tailwind CSS** - Styling
- **React Router** - Routing
- **AOS** - Scroll animations

## Development

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Project Structure

```
src/
├── components/     # Reusable components
│   └── Header.tsx  # Navigation header
├── pages/          # Page components
│   └── Home.tsx    # Home page
├── data/           # Data files and configs
├── App.tsx         # Main app with routing
├── main.tsx        # Entry point
└── index.css       # Global styles with Tailwind
```

## Features

- ✅ Responsive navigation with mobile menu
- ✅ Lazy loading images for performance
- ✅ Smooth scroll animations with AOS
- ✅ Tailwind CSS for modern styling
- ✅ TypeScript for type safety
- ✅ Fast development with Vite + Rolldown

## Migration Status

### Completed
- ✅ Project setup with React + Vite + TypeScript
- ✅ Tailwind CSS configuration
- ✅ Navigation header component
- ✅ Home page with hero section
- ✅ React Router setup

### In Progress
- 🔄 About, Events, Blog, Dandelion, Contact pages
- 🔄 Blog post components and data
- 🔄 Event detail pages
- 🔄 Dandelion magazine viewer

## Legacy Files

The original HTML/CSS files are preserved in the root directory. The React version is being built in the `src/` directory.

## Deployment

Built files will be in the `dist/` directory after running `npm run build`.

## License

© 2025 English Literary Society, IIT Kanpur
