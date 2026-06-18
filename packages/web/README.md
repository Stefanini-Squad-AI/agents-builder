# Agents Workshop Web UI

Next.js 14 web interface for the Agents Workshop tool - an AI-powered platform for generating programming skills and Jira card workflows.

## Features

- ✅ Next.js 14 with App Router
- ✅ Tailwind CSS for styling
- ✅ shadcn/ui component library
- ✅ Dark mode support with next-themes
- ✅ TypeScript for type safety
- ✅ Responsive design
- 🔄 Backend API integration (coming in Step 2.2)

## Getting Started

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Run the development server:**
   ```bash
   npm run dev
   ```

3. **Open your browser:**
   Visit [http://localhost:3000](http://localhost:3000)

## Project Structure

```
src/
├── app/              # Next.js 14 App Router
│   ├── layout.tsx    # Root layout with theme provider
│   ├── page.tsx      # Home page
│   └── globals.css   # Global styles and CSS variables
├── components/       # React components
│   ├── ui/          # shadcn/ui components
│   │   └── button.tsx
│   ├── theme-provider.tsx
│   └── theme-toggle.tsx
└── lib/
    └── utils.ts      # Utility functions
```

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run start` - Start production server
- `npm run lint` - Run ESLint
- `npm run type-check` - Run TypeScript compiler

## Technology Stack

- **Framework:** Next.js 14
- **Styling:** Tailwind CSS
- **Components:** shadcn/ui + Radix UI
- **Icons:** Lucide React
- **Theme:** next-themes
- **Language:** TypeScript

## Environment Variables

Copy `.env.example` to `.env.local` and configure:

- `NEXT_PUBLIC_API_URL` - Backend API URL (default: http://localhost:8000)

## Next Steps (Phase 2)

- Step 2.2: API client integration (Axios + TanStack Query)
- Step 2.3: Authentication layer
- Step 2.4: Project management interface
- Step 2.5: Skill and card builders