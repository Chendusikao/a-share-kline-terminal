# Couple Travel Road-Film Website Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a public, responsive travel portfolio that tells three years of couple trips as a daylight road film, with chapter browsing, six shareable places, a route map, and accessible photo viewing.

**Architecture:** Next.js App Router renders static pages from typed local travel content. A small content/query layer supplies chapters, places, and media to focused visual components; UI state is limited to gallery, filters, and reduced-motion preference. Enhanced movement is optional, while every route remains fully usable with static media.

**Tech Stack:** Next.js App Router, React, TypeScript, CSS Modules, Vitest, React Testing Library, Playwright, next/image.

## Global Constraints

- Public scope is a travel work portfolio, not a private diary; do not add accounts, comments, uploads, or original-image downloads.
- Use the approved daylight road-film visual system: cream `#F5EFE3`, road blue-gray `#1C3340`, sun gold `#D9B778`, sign orange `#A2644E`, vegetation green `#576A4E`.
- Preserve daylight images; do not apply a site-wide dark filter or auto-play video/audio.
- Keep four primary navigation entries: 首页, 旅程章节, 旅程地图, 全部片段.
- Support 2024 天津滨江道/天津滨海新区, 2025 北戴河/北京, 2026 济南/南京 as three chapters with two stops each.
- Provide keyboard access, meaningful image alt text, `prefers-reduced-motion` support, and static fallbacks for every enhanced interaction.
- Store only city/attraction-level coordinates. Do not expose EXIF, precise GPS, device metadata, or original media URLs.
- Do not add a WebGL dependency in this release; 3D is a later optional enhancement.

---

## File Structure

```text
src/
  app/
    layout.tsx                 Root metadata, fonts, header/footer shell
    page.tsx                   Home: hero plus chapter sequence
    journeys/page.tsx          Full chapter index
    map/page.tsx               Route map and place jump list
    moments/page.tsx           Filterable photo collection
    places/[slug]/page.tsx     Static, shareable place page
    not-found.tsx              Unknown-place recovery
  components/
    layout/SiteHeader.tsx      Four-entry navigation and mobile menu
    layout/SiteFooter.tsx      Credits/privacy notice
    journey/Hero.tsx           Daylight road-film first screen
    journey/ChapterSection.tsx Chapter poster, narration and stop links
    journey/PlaceStopCard.tsx  Accessible destination entry point
    map/RouteMap.tsx           SVG route and static place list fallback
    gallery/MomentGrid.tsx     Filterable image grid
    gallery/Lightbox.tsx       Keyboard-accessible modal gallery
    ui/MotionPreference.tsx    Reduced-motion control persisted locally
  content/travel.ts            Approved chapters, places and media metadata
  lib/travel.ts                Pure lookup/filter/navigation functions
  types/travel.ts              Chapter, Place and Media types
  styles/*.module.css          Component-scoped responsive presentation
tests/
  unit/travel.test.ts
  components/Lightbox.test.tsx
  components/RouteMap.test.tsx
e2e/
  home.spec.ts
  places.spec.ts
  accessibility.spec.ts
```

### Task 1: Bootstrap the App Router project and test harness

**Files:**
- Create: `package.json`, `tsconfig.json`, `next.config.ts`, `src/app/layout.tsx`, `src/app/page.tsx`
- Create: `vitest.config.ts`, `tests/setup.ts`, `playwright.config.ts`, `e2e/home.spec.ts`
- Modify: `.gitignore`

**Interfaces:**
- Produces the `@/*` TypeScript alias and `npm run dev`, `npm run test`, `npm run test:e2e`, `npm run lint` scripts used by all later tasks.

- [ ] **Step 1: Create the failing smoke test**

```ts
// e2e/home.spec.ts
import { expect, test } from '@playwright/test';

test('opens the travel portfolio home page', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `npm run test:e2e -- e2e/home.spec.ts`

Expected: FAIL because no Next.js application or home route exists.

- [ ] **Step 3: Scaffold the minimal application and scripts**

```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "eslint .",
    "test": "vitest run",
    "test:e2e": "playwright test"
  }
}
```

Create `src/app/page.tsx` with one `<h1>旅程正在路上</h1>`, then configure Playwright `webServer.command` as `npm run dev` and Vitest with the jsdom environment and `tests/setup.ts` importing `@testing-library/jest-dom/vitest`.

- [ ] **Step 4: Run the smoke test and lint**

Run: `npm run test:e2e -- e2e/home.spec.ts && npm run lint`

Expected: PASS with a visible level-one heading and no lint errors.

- [ ] **Step 5: Commit**

```bash
git add package.json tsconfig.json next.config.ts vitest.config.ts playwright.config.ts src/app tests e2e .gitignore
git commit -m "chore: scaffold travel portfolio app"
```

### Task 2: Add typed travel content and pure content queries

**Files:**
- Create: `src/types/travel.ts`, `src/content/travel.ts`, `src/lib/travel.ts`, `tests/unit/travel.test.ts`

**Interfaces:**
- Produces `Chapter`, `Place`, `Media`, `chapters`, `places`, `media`, `getPlaceBySlug(slug)`, `getChapterByYear(year)`, `getPlacesForChapter(chapterId)`, and `getAdjacentPlaces(slug)`.
- Consumes no UI code; later routes import only from `@/lib/travel`.

- [ ] **Step 1: Write failing query tests**

```ts
import { getAdjacentPlaces, getPlaceBySlug } from '@/lib/travel';

it('finds the six approved place records by shareable slug', () => {
  expect(getPlaceBySlug('tianjin-binjing-road')?.name).toBe('天津滨江道');
  expect(getPlaceBySlug('nanjing')?.year).toBe(2026);
});

it('returns deterministic previous and next stops', () => {
  expect(getAdjacentPlaces('beidaihe')).toEqual({ previous: 'tianjin-binhai', next: 'beijing' });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `npm run test -- tests/unit/travel.test.ts`

Expected: FAIL with unresolved `@/lib/travel`.

- [ ] **Step 3: Implement immutable content and lookup functions**

```ts
export type Place = {
  id: string; slug: string; chapterId: string; year: 2024 | 2025 | 2026;
  name: string; city: string; dateLabel: string; summary: string;
  heroMediaId: string; mediaIds: string[]; coordinates: [number, number];
};

export function getPlaceBySlug(slug: string) {
  return places.find((place) => place.slug === slug);
}
```

Populate all three chapters and six places. Use illustrative local asset paths such as `/images/places/nanjing-01.webp`; never insert original image URLs or precise coordinates. Implement adjacent navigation from the single ordered `places` list.

- [ ] **Step 4: Run unit tests**

Run: `npm run test -- tests/unit/travel.test.ts`

Expected: PASS; all six slugs resolve and adjacent stops are stable.

- [ ] **Step 5: Commit**

```bash
git add src/types/travel.ts src/content/travel.ts src/lib/travel.ts tests/unit/travel.test.ts
git commit -m "feat: add typed travel content"
```

### Task 3: Build the shared shell, navigation, motion preference and visual tokens

**Files:**
- Create: `src/components/layout/SiteHeader.tsx`, `src/components/layout/SiteFooter.tsx`, `src/components/ui/MotionPreference.tsx`, `src/styles/globals.css`, `src/styles/shell.module.css`
- Modify: `src/app/layout.tsx`
- Test: `tests/components/MotionPreference.test.tsx`

**Interfaces:**
- Produces `SiteHeader`, `SiteFooter`, and `MotionPreference`; the root `<html>` receives `data-reduced-motion="true" | "false"`.
- Consumes the four fixed route labels and browser `localStorage` key `travel-motion-preference`.

- [ ] **Step 1: Write the failing preference test**

```tsx
render(<MotionPreference />);
await user.click(screen.getByRole('switch', { name: '减少动态效果' }));
expect(document.documentElement.dataset.reducedMotion).toBe('true');
expect(localStorage.getItem('travel-motion-preference')).toBe('reduce');
```

- [ ] **Step 2: Run it to verify it fails**

Run: `npm run test -- tests/components/MotionPreference.test.tsx`

Expected: FAIL because the component does not exist.

- [ ] **Step 3: Implement the shell and accessible preference control**

```tsx
<button role="switch" aria-checked={reduced} aria-label="减少动态效果" onClick={toggle}>
  减少动态效果
</button>
```

Define the approved colors as CSS custom properties. Add `@media (prefers-reduced-motion: reduce)` and `[data-reduced-motion='true']` rules that set transition and animation duration to `0ms`. Render the header navigation links to `/`, `/journeys`, `/map`, `/moments`, then the preference control and footer from `layout.tsx`.

- [ ] **Step 4: Run component tests and lint**

Run: `npm run test -- tests/components/MotionPreference.test.tsx && npm run lint`

Expected: PASS; the toggle persists a reduced-motion choice.

- [ ] **Step 5: Commit**

```bash
git add src/app/layout.tsx src/components src/styles tests/components/MotionPreference.test.tsx
git commit -m "feat: add accessible portfolio shell"
```

### Task 4: Implement the road-film home and chapter experience

**Files:**
- Create: `src/components/journey/Hero.tsx`, `src/components/journey/ChapterSection.tsx`, `src/components/journey/PlaceStopCard.tsx`, `src/styles/journey.module.css`
- Modify: `src/app/page.tsx`, `src/app/journeys/page.tsx`
- Test: `e2e/home.spec.ts`

**Interfaces:**
- Consumes `Chapter`, `Place`, `getPlacesForChapter` and `MotionPreference`.
- Produces static links with accessible names `查看{place.name}` for all six location stops.

- [ ] **Step 1: Extend the failing home flow test**

```ts
await expect(page.getByText('从天津，第一次出发。')).toBeVisible();
await page.getByRole('link', { name: '查看北戴河' }).click();
await expect(page).toHaveURL(/\/places\/beidaihe$/);
```

- [ ] **Step 2: Run it to verify it fails**

Run: `npm run test:e2e -- e2e/home.spec.ts`

Expected: FAIL because chapters and place links are absent.

- [ ] **Step 3: Render the hero and three chapter sections**

```tsx
{chapters.map((chapter) => (
  <ChapterSection key={chapter.id} chapter={chapter} places={getPlacesForChapter(chapter.id)} />
))}
```

Use a full-bleed hero image with the title “The long way felt like home.” and a visible “进入旅程” anchor. Each section must render the exact approved title, narration, two stop cards, and a next-chapter cue. CSS may use opacity and transform transitions only when motion is permitted.

- [ ] **Step 4: Run the home flow test**

Run: `npm run test:e2e -- e2e/home.spec.ts`

Expected: PASS; all three chapter titles render and 北戴河 links to its place route.

- [ ] **Step 5: Commit**

```bash
git add src/app/page.tsx src/app/journeys/page.tsx src/components/journey src/styles/journey.module.css e2e/home.spec.ts
git commit -m "feat: add road film chapters"
```

### Task 5: Implement static, shareable place pages and unknown-place recovery

**Files:**
- Create: `src/app/places/[slug]/page.tsx`, `src/app/places/[slug]/loading.tsx`, `src/app/places/[slug]/not-found.tsx`, `src/app/not-found.tsx`, `src/styles/place.module.css`
- Test: `e2e/places.spec.ts`

**Interfaces:**
- Consumes `getPlaceBySlug`, `getAdjacentPlaces`, `getPlacesForChapter`, and `Media`.
- Produces statically generated `/places/[slug]` pages and 404 recovery for unknown slugs.

- [ ] **Step 1: Write failing route tests**

```ts
test('a place page has a shareable title and adjacent navigation', async ({ page }) => {
  await page.goto('/places/jinan');
  await expect(page.getByRole('heading', { name: '济南' })).toBeVisible();
  await expect(page.getByRole('link', { name: '下一站：南京' })).toBeVisible();
});

test('unknown slugs show recovery', async ({ page }) => {
  await page.goto('/places/not-a-place');
  await expect(page.getByRole('link', { name: '返回旅程章节' })).toBeVisible();
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `npm run test:e2e -- e2e/places.spec.ts`

Expected: FAIL because the dynamic route is absent.

- [ ] **Step 3: Implement static params, metadata and recovery**

```ts
export function generateStaticParams() {
  return places.map(({ slug }) => ({ slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const place = getPlaceBySlug((await params).slug);
  return { title: place ? `${place.name}｜旅程正在路上` : '地点未找到｜旅程正在路上' };
}
```

Render city-level dates, story, hero image with alt text, in-chapter media, previous/next links, and a “返回旅程章节” link. Call `notFound()` when lookup fails. The loading state must be text-and-shape based, not a blank page.

- [ ] **Step 4: Run route tests and production build**

Run: `npm run test:e2e -- e2e/places.spec.ts && npm run build`

Expected: PASS; all six routes statically build and unknown pages recover.

- [ ] **Step 5: Commit**

```bash
git add src/app/places src/app/not-found.tsx src/styles/place.module.css e2e/places.spec.ts
git commit -m "feat: add shareable place pages"
```

### Task 6: Add the map route and filterable moments collection

**Files:**
- Create: `src/components/map/RouteMap.tsx`, `src/components/gallery/MomentGrid.tsx`, `src/app/map/page.tsx`, `src/app/moments/page.tsx`, `src/styles/map.module.css`, `src/styles/gallery.module.css`
- Test: `tests/components/RouteMap.test.tsx`, `e2e/moments.spec.ts`

**Interfaces:**
- Consumes `places`, `media`, `getPlaceBySlug`.
- Produces a semantic map list with six destination links and a gallery filter using URL parameter `?year=2024|2025|2026|all`.

- [ ] **Step 1: Write failing fallback and filtering tests**

```tsx
render(<RouteMap places={places} />);
expect(screen.getByRole('list', { name: '旅程地点列表' })).toHaveTextContent('天津滨江道');
expect(screen.getAllByRole('link', { name: /查看/ })).toHaveLength(6);
```

```ts
await page.goto('/moments?year=2025');
await expect(page.getByText('北戴河')).toBeVisible();
await expect(page.getByText('天津滨江道')).not.toBeVisible();
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm run test -- tests/components/RouteMap.test.tsx && npm run test:e2e -- e2e/moments.spec.ts`

Expected: FAIL because map and moments routes do not exist.

- [ ] **Step 3: Implement SVG enhancement with semantic fallback**

```tsx
<nav aria-label="旅程地点列表">
  <ul>{places.map((place) => <li key={place.id}><Link href={`/places/${place.slug}`}>查看{place.name}</Link></li>)}</ul>
</nav>
```

Draw a decorative SVG line behind the list only; map interaction must never be the sole navigation method. On `/moments`, read `searchParams.year`, reject unsupported values to `all`, and render year links that preserve the accessible collection heading.

- [ ] **Step 4: Run map and collection tests**

Run: `npm run test -- tests/components/RouteMap.test.tsx && npm run test:e2e -- e2e/moments.spec.ts`

Expected: PASS; the map fallback has six links and the 2025 filter excludes 2024 items.

- [ ] **Step 5: Commit**

```bash
git add src/components/map src/components/gallery src/app/map src/app/moments src/styles/map.module.css src/styles/gallery.module.css tests/components/RouteMap.test.tsx e2e/moments.spec.ts
git commit -m "feat: add map and moments browsing"
```

### Task 7: Add an accessible photo lightbox and image failure fallback

**Files:**
- Create: `src/components/gallery/Lightbox.tsx`, `src/components/gallery/MediaImage.tsx`, `tests/components/Lightbox.test.tsx`
- Modify: `src/components/gallery/MomentGrid.tsx`, `src/app/places/[slug]/page.tsx`

**Interfaces:**
- Consumes `Media[]` where every media item has `alt`, `thumbnailUrl`, and public derivative `url`.
- Produces `Lightbox({ media, initialIndex, onClose })` with Escape close, next/previous controls and image-error description fallback.

- [ ] **Step 1: Write failing keyboard and fallback tests**

```tsx
render(<Lightbox media={media} initialIndex={0} onClose={onClose} />);
await user.keyboard('{ArrowRight}');
expect(screen.getByRole('img')).toHaveAccessibleName(media[1].alt);
await user.keyboard('{Escape}');
expect(onClose).toHaveBeenCalledOnce();
```

```tsx
fireEvent.error(screen.getByRole('img', { name: media[0].alt }));
expect(screen.getByText(media[0].alt)).toBeVisible();
```

- [ ] **Step 2: Run it to verify it fails**

Run: `npm run test -- tests/components/Lightbox.test.tsx`

Expected: FAIL because the gallery components do not exist.

- [ ] **Step 3: Implement a dialog with deterministic controls**

```tsx
<dialog open aria-label="照片查看器" onKeyDown={onKeyDown}>
  <button onClick={onClose} aria-label="关闭照片查看器">关闭</button>
  <button onClick={showPrevious} aria-label="上一张照片">上一张</button>
  <MediaImage media={currentMedia} />
  <button onClick={showNext} aria-label="下一张照片">下一张</button>
</dialog>
```

Trap focus inside the dialog, restore focus to the opening thumbnail on close, and use `onError` in `MediaImage` to replace the failed image with its alt text plus “照片暂时无法显示”. Never render an original download link.

- [ ] **Step 4: Run component tests**

Run: `npm run test -- tests/components/Lightbox.test.tsx`

Expected: PASS; keyboard navigation, Escape close, and failed-image text all work.

- [ ] **Step 5: Commit**

```bash
git add src/components/gallery tests/components/Lightbox.test.tsx src/app/places/[slug]/page.tsx
git commit -m "feat: add accessible photo viewer"
```

### Task 8: Verify accessibility, responsive behavior, privacy and production output

**Files:**
- Create: `e2e/accessibility.spec.ts`, `README.md`
- Modify: all files only where the tests expose a concrete defect

**Interfaces:**
- Consumes all completed routes and the public metadata model.
- Produces documented local setup, content replacement instructions, and a passing release gate.

- [ ] **Step 1: Write failing release-gate tests**

```ts
test('keyboard users can reach every primary route', async ({ page }) => {
  await page.goto('/');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('navigation', { name: '主导航' })).toBeFocused();
  await expect(page.getByRole('link', { name: '旅程地图' })).toBeVisible();
});

test('reduced motion preference is reflected in the document', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  await expect(page.locator('html')).toHaveAttribute('data-reduced-motion', 'true');
});
```

- [ ] **Step 2: Run it to identify gaps**

Run: `npm run test:e2e -- e2e/accessibility.spec.ts`

Expected: FAIL until focus semantics and initial system preference handling are complete.

- [ ] **Step 3: Fix only the reported release defects and document operations**

Implement initial `matchMedia('(prefers-reduced-motion: reduce)')` detection before the preference control is rendered. Add README sections for asset placement under `public/images/places`, required alt text, EXIF stripping before export, build commands, and the six supported content slugs.

- [ ] **Step 4: Run the complete release gate**

Run: `npm run lint && npm run test && npm run build && npm run test:e2e`

Expected: all commands exit `0`; every public route, fallback, keyboard flow, reduced-motion mode, and static build succeeds.

- [ ] **Step 5: Commit**

```bash
git add README.md e2e/accessibility.spec.ts src
git commit -m "test: verify accessible travel portfolio release"
```

## Self-Review

- **Spec coverage:** Tasks 2 and 4 implement the three approved yearly chapters and six stops; Tasks 4–6 implement the four-entry browsing architecture; Task 3 implements visual tokens and reduced motion; Task 7 covers photo viewing and image errors; Tasks 5–6 provide static fallback routes and semantic map links; Task 8 verifies responsive/accessibility/privacy operations. The explicit non-goals and 3D deferral are enforced by the global constraints.
- **Placeholder scan:** This plan contains no open-ended implementation markers. All tests, commands, function names, route names, content slugs and commits are explicit.
- **Type consistency:** `Place.slug`, `Place.chapterId`, `Media.alt`, `getPlaceBySlug`, `getPlacesForChapter`, and `getAdjacentPlaces` are introduced in Task 2 and consumed with the same names in Tasks 4–7.
