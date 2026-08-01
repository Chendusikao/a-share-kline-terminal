# Final weight normalization fix

## RED

Added a regression test for raw weights `100051, 200051, 300051, 399837, 10`.

Command:

```powershell
cd frontend
npm test -- --run tests/config.test.ts
```

Result before the implementation: exit code 1. The new test failed at the
non-negative assertion because the last-positive residual was negative.

## GREEN

Normalization now scales values by their largest input to avoid an overflowing
sum, then assigns the rounding residual to the largest weight. With five
non-negative weights, the largest displayed share is at least 20%, so it can
absorb the at-most 0.02% aggregate rounding adjustment from the other four
weights without becoming negative.

Commands and results after the implementation:

```powershell
cd frontend
npm test -- --run tests/config.test.ts  # 3 passed
npm test                                # 29 passed
npm run typecheck                       # exit 0
npm run build                           # exit 0
```

The production build emitted Vite's existing chunk-size warning for a
minified JavaScript chunk above 500 kB; it does not affect the weight fix.
