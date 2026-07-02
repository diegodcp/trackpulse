import { Graphics, Text, Container } from 'pixi.js';

export class CarMarkerSprite {
  container: Container;
  private circle: Graphics;
  private label: Text;
  private readonly radius = 10;

  constructor(teamColour: string, nameAcronym: string) {
    this.container = new Container();

    // Colored circle
    this.circle = new Graphics();
    this.circle.circle(0, 0, this.radius);
    this.circle.fill({ color: parseInt(teamColour, 16) });
    this.container.addChild(this.circle);

    // Driver abbreviation label
    this.label = new Text({
      text: nameAcronym,
      style: { fontSize: 9, fill: 0xffffff, fontWeight: 'bold' },
    });
    this.label.anchor.set(0.5);
    this.label.y = -this.radius - 8;
    this.container.addChild(this.label);
  }

  updatePosition(screenX: number, screenY: number) {
    this.container.x = screenX;
    this.container.y = screenY;
  }

  setActive(active: boolean) {
    this.container.alpha = active ? 1.0 : 0.3;
  }

  setInPit(inPit: boolean) {
    this.container.alpha = inPit ? 0.5 : 1.0;
  }

  destroy() {
    this.container.destroy({ children: true });
  }
}
