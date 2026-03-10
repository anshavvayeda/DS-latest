import React, { useEffect, useRef } from 'react';

export function Galaxy({
  starSpeed = 0.5,
  density = 1,
  hueShift = 140,
  speed = 1,
  glowIntensity = 0.3,
  saturation = 0,
  mouseRepulsion = true,
  repulsionStrength = 0.5,
  twinkleIntensity = 0.3,
  rotationSpeed = 0.1,
  transparent = true,
  className = '',
}) {
  const canvasRef = useRef(null);
  const mouseRef = useRef({ x: 0, y: 0 });
  const animationRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let stars = [];
    let w = window.innerWidth;
    let h = window.innerHeight;

    // Set canvas size
    const resizeCanvas = () => {
      w = window.innerWidth;
      h = window.innerHeight;
      canvas.width = w;
      canvas.height = h;
      initStars();
    };

    // Star class
    class Star {
      constructor() {
        this.reset();
      }

      reset() {
        this.x = Math.random() * w;
        this.y = Math.random() * h;
        this.z = Math.random() * 1000;
        this.vz = starSpeed * speed;
        this.radius = Math.random() * 1.5 + 0.5;
        this.hue = hueShift + Math.random() * 60;
        this.opacity = Math.random() * 0.5 + 0.5;
        this.twinkleSpeed = Math.random() * 0.05 * twinkleIntensity;
        this.twinklePhase = Math.random() * Math.PI * 2;
      }

      update(mouseX, mouseY) {
        // Move star forward
        this.z -= this.vz;
        if (this.z <= 0) {
          this.reset();
          this.z = 1000;
        }

        // Mouse repulsion
        if (mouseRepulsion) {
          const dx = this.x - mouseX;
          const dy = this.y - mouseY;
          const distance = Math.sqrt(dx * dx + dy * dy);
          
          if (distance < 200) {
            const force = (200 - distance) / 200 * repulsionStrength;
            this.x += (dx / distance) * force * 3;
            this.y += (dy / distance) * force * 3;
          }
        }

        // Rotation effect
        const centerX = w / 2;
        const centerY = h / 2;
        const angleSpeed = rotationSpeed * 0.001;
        const dx = this.x - centerX;
        const dy = this.y - centerY;
        const angle = Math.atan2(dy, dx);
        const newAngle = angle + angleSpeed;
        const distance = Math.sqrt(dx * dx + dy * dy);
        
        this.x = centerX + Math.cos(newAngle) * distance;
        this.y = centerY + Math.sin(newAngle) * distance;

        // Twinkle effect
        this.twinklePhase += this.twinkleSpeed;
        this.opacity = 0.5 + Math.sin(this.twinklePhase) * 0.3 * twinkleIntensity;
      }

      draw() {
        const sx = (this.x - w / 2) * (1000 / this.z) + w / 2;
        const sy = (this.y - h / 2) * (1000 / this.z) + h / 2;
        const size = (1 - this.z / 1000) * this.radius * 3;

        if (sx < 0 || sx > w || sy < 0 || sy > h) {
          return;
        }

        const brightness = 1 - this.z / 1000;
        const sat = saturation * 100;
        const glow = glowIntensity * brightness * 10;

        ctx.beginPath();
        ctx.arc(sx, sy, size, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${this.hue}, ${sat}%, ${brightness * 100}%, ${this.opacity})`;
        ctx.shadowBlur = glow;
        ctx.shadowColor = `hsla(${this.hue}, ${sat}%, ${brightness * 100}%, ${this.opacity})`;
        ctx.fill();
      }
    }

    // Initialize stars
    const initStars = () => {
      const starCount = Math.floor((w * h) / 10000 * density);
      stars = [];
      for (let i = 0; i < starCount; i++) {
        stars.push(new Star());
      }
    };

    // Mouse move handler
    const handleMouseMove = (e) => {
      mouseRef.current = {
        x: e.clientX,
        y: e.clientY,
      };
    };

    // Animation loop
    const animate = () => {
      if (!transparent) {
        ctx.fillStyle = 'rgba(11, 15, 26, 0.2)';
        ctx.fillRect(0, 0, w, h);
      } else {
        ctx.clearRect(0, 0, w, h);
      }

      stars.forEach(star => {
        star.update(mouseRef.current.x, mouseRef.current.y);
        star.draw();
      });

      animationRef.current = requestAnimationFrame(animate);
    };

    // Initialize
    resizeCanvas();
    animate();

    // Event listeners
    window.addEventListener('resize', resizeCanvas);
    if (mouseRepulsion) {
      window.addEventListener('mousemove', handleMouseMove);
    }

    // Cleanup
    return () => {
      window.removeEventListener('resize', resizeCanvas);
      window.removeEventListener('mousemove', handleMouseMove);
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [starSpeed, density, hueShift, speed, glowIntensity, saturation, mouseRepulsion, repulsionStrength, twinkleIntensity, rotationSpeed, transparent]);

  return (
    <canvas
      ref={canvasRef}
      className={`block ${className}`}
      style={{
        width: '100%',
        height: '100%',
        position: 'absolute',
        top: 0,
        left: 0,
      }}
    />
  );
}
