export default function Home() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-2xl flex-col items-center justify-center gap-6 px-4 text-center">
      <span className="rounded-full border border-border bg-muted px-3 py-1 text-sm text-muted-foreground">
        Foundation ready
      </span>
      <h1 className="text-4xl font-bold tracking-tight">ShopFlow</h1>
      <p className="text-balance text-muted-foreground">
        Frontend scaffold: Next.js App Router, TypeScript (strict), Tailwind v3
        with CSS-variable theming, TanStack Query, Zustand, React Hook Form +
        Zod, MSW, and Storybook. Components and pages come next.
      </p>
      <div className="flex flex-wrap items-center justify-center gap-3">
        <button className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90">
          Primary
        </button>
        <button className="rounded-md border border-input bg-background px-4 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground">
          Secondary
        </button>
      </div>
    </main>
  );
}
