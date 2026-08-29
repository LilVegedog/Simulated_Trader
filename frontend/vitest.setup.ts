import "@testing-library/jest-dom/vitest";

// jsdom has no layout engine; charts only need the observer to exist.
globalThis.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};
