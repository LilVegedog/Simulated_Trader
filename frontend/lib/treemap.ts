export interface TreemapItem {
  key: string;
  value: number;
}

export interface TreemapTile extends TreemapItem {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}

const worst = (row: number[], length: number, scale: number) => {
  const sum = row.reduce((a, b) => a + b, 0) * scale;
  const max = Math.max(...row) * scale;
  const min = Math.min(...row) * scale;
  return Math.max((length * length * max) / (sum * sum), (sum * sum) / (length * length * min));
};

/** Squarified treemap layout: tiles are ordered largest-first and kept near-square. */
export function squarify(items: TreemapItem[], width: number, height: number): TreemapTile[] {
  const sorted = [...items].filter((i) => i.value > 0).sort((a, b) => b.value - a.value);
  const total = sorted.reduce((a, b) => a + b.value, 0);
  if (total === 0 || width <= 0 || height <= 0) return [];

  const scale = (width * height) / total;
  const tiles: TreemapTile[] = [];
  let box: Box = { x: 0, y: 0, width, height };
  let row: TreemapItem[] = [];
  let index = 0;

  const layoutRow = () => {
    const length = Math.min(box.width, box.height);
    const area = row.reduce((a, b) => a + b.value, 0) * scale;
    const thickness = area / length;
    let offset = 0;
    for (const item of row) {
      const size = (item.value * scale) / thickness;
      tiles.push(
        box.width >= box.height
          ? { ...item, x: box.x, y: box.y + offset, width: thickness, height: size }
          : { ...item, x: box.x + offset, y: box.y, width: size, height: thickness },
      );
      offset += size;
    }
    box =
      box.width >= box.height
        ? { x: box.x + thickness, y: box.y, width: box.width - thickness, height: box.height }
        : { x: box.x, y: box.y + thickness, width: box.width, height: box.height - thickness };
    row = [];
  };

  while (index < sorted.length) {
    const length = Math.min(box.width, box.height);
    const current = row.map((i) => i.value);
    const next = [...current, sorted[index].value];
    if (row.length === 0 || worst(next, length, scale) <= worst(current, length, scale)) {
      row.push(sorted[index]);
      index += 1;
    } else {
      layoutRow();
    }
  }
  if (row.length > 0) layoutRow();
  return tiles;
}
