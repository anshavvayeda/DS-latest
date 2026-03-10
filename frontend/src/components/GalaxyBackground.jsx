import { Galaxy } from "@/components/ui/galaxy";

export default function GalaxyBackground() {
  return (
    <div className="fixed inset-0 -z-10 pointer-events-none">
      <Galaxy
        starSpeed={0.7}
        density={4}
        hueShift={140}
        speed={1.5}
        glowIntensity={5}
        saturation={0}
        mouseRepulsion
        repulsionStrength={2}
        twinkleIntensity={0.3}
        rotationSpeed={0.2}
        transparent
      />
    </div>
  );
}
