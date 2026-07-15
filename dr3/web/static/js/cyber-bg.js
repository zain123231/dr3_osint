/**
 * DR3 Intelligence Platform — Cyber Background Engine
 * 
 * Renders a subtle animated background inspired by:
 * - Matrix rain (very subtle green characters)
 * - Floating particles with connection lines
 * - Hexagonal grid overlay
 * 
 * Performance-optimized:
 * - Uses requestAnimationFrame
 * - Pauses when tab is hidden
 * - Respects prefers-reduced-motion
 * - Automatically adjusts density based on viewport
 */

class CyberBackground {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;

        this.ctx = this.canvas.getContext('2d');
        this.particles = [];
        this.matrixDrops = [];
        this.running = true;
        this.frameCount = 0;

        // Check for reduced motion preference
        this.reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        // Configuration
        this.config = {
            particleCount: 40,
            particleSpeed: 0.15,
            connectionDistance: 150,
            matrixDensity: 25,    // columns
            matrixSpeed: 0.4,
            matrixOpacity: 0.04,  // Very subtle
            particleOpacity: 0.12,
            connectionOpacity: 0.04,
            colors: {
                matrix: '#00ff66',
                particle: '#00eaff',
                connection: '#00eaff',
            }
        };

        this.init();
    }

    init() {
        if (this.reduceMotion) {
            // Static subtle grid only
            this.resize();
            this.drawStaticGrid();
            return;
        }

        this.resize();
        this.initParticles();
        this.initMatrix();

        window.addEventListener('resize', () => this.resize());

        // Pause when tab is hidden
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.running = false;
            } else {
                this.running = true;
                this.animate();
            }
        });

        this.animate();
    }

    resize() {
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        this.width = window.innerWidth;
        this.height = window.innerHeight;
        this.canvas.width = this.width * dpr;
        this.canvas.height = this.height * dpr;
        this.canvas.style.width = this.width + 'px';
        this.canvas.style.height = this.height + 'px';
        this.ctx.scale(dpr, dpr);

        // Adjust density for mobile
        if (this.width < 768) {
            this.config.particleCount = 15;
            this.config.matrixDensity = 10;
        }
    }

    // ── Particle System ──
    initParticles() {
        this.particles = [];
        for (let i = 0; i < this.config.particleCount; i++) {
            this.particles.push({
                x: Math.random() * this.width,
                y: Math.random() * this.height,
                vx: (Math.random() - 0.5) * this.config.particleSpeed,
                vy: (Math.random() - 0.5) * this.config.particleSpeed,
                size: Math.random() * 2 + 0.5,
                opacity: Math.random() * 0.5 + 0.3,
            });
        }
    }

    updateParticles() {
        for (const p of this.particles) {
            p.x += p.vx;
            p.y += p.vy;

            // Wrap around edges
            if (p.x < 0) p.x = this.width;
            if (p.x > this.width) p.x = 0;
            if (p.y < 0) p.y = this.height;
            if (p.y > this.height) p.y = 0;
        }
    }

    drawParticles() {
        const ctx = this.ctx;

        // Draw connections first (behind particles)
        for (let i = 0; i < this.particles.length; i++) {
            for (let j = i + 1; j < this.particles.length; j++) {
                const a = this.particles[i];
                const b = this.particles[j];
                const dx = a.x - b.x;
                const dy = a.y - b.y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < this.config.connectionDistance) {
                    const opacity = (1 - dist / this.config.connectionDistance) * this.config.connectionOpacity;
                    ctx.strokeStyle = `rgba(0, 234, 255, ${opacity})`;
                    ctx.lineWidth = 0.5;
                    ctx.beginPath();
                    ctx.moveTo(a.x, a.y);
                    ctx.lineTo(b.x, b.y);
                    ctx.stroke();
                }
            }
        }

        // Draw particles
        for (const p of this.particles) {
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(0, 234, 255, ${p.opacity * this.config.particleOpacity})`;
            ctx.fill();

            // Subtle glow
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.size * 3, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(0, 234, 255, ${p.opacity * 0.02})`;
            ctx.fill();
        }
    }

    // ── Matrix Rain ──
    initMatrix() {
        this.matrixDrops = [];
        const columns = this.config.matrixDensity;
        const colWidth = this.width / columns;

        for (let i = 0; i < columns; i++) {
            this.matrixDrops.push({
                x: i * colWidth + colWidth / 2,
                y: Math.random() * this.height * -1,
                speed: this.config.matrixSpeed + Math.random() * 0.3,
                chars: this.generateMatrixColumn(),
                charIndex: 0,
                opacity: Math.random() * 0.5 + 0.5,
            });
        }
    }

    generateMatrixColumn() {
        const chars = '01アイウエオカキクケコ♦◊□△▽○●◆◇';
        const length = Math.floor(Math.random() * 12) + 5;
        let result = '';
        for (let i = 0; i < length; i++) {
            result += chars[Math.floor(Math.random() * chars.length)];
        }
        return result;
    }

    drawMatrix() {
        const ctx = this.ctx;
        ctx.font = '12px "JetBrains Mono", monospace';

        for (const drop of this.matrixDrops) {
            // Draw each character in the trail
            for (let i = 0; i < drop.chars.length; i++) {
                const y = drop.y - i * 16;
                if (y < -20 || y > this.height + 20) continue;

                const fadeOpacity = i === 0
                    ? this.config.matrixOpacity * drop.opacity
                    : this.config.matrixOpacity * drop.opacity * (1 - i / drop.chars.length) * 0.6;

                if (fadeOpacity < 0.005) continue;

                ctx.fillStyle = `rgba(0, 255, 102, ${fadeOpacity})`;
                ctx.fillText(drop.chars[i], drop.x, y);
            }

            // Move drop down
            drop.y += drop.speed;

            // Reset when off screen
            if (drop.y - drop.chars.length * 16 > this.height) {
                drop.y = Math.random() * -200;
                drop.chars = this.generateMatrixColumn();
                drop.opacity = Math.random() * 0.5 + 0.5;
            }
        }
    }

    // ── Static Grid (for reduced motion) ──
    drawStaticGrid() {
        const ctx = this.ctx;
        ctx.strokeStyle = 'rgba(0, 234, 255, 0.02)';
        ctx.lineWidth = 0.5;

        const gridSize = 60;
        for (let x = 0; x < this.width; x += gridSize) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, this.height);
            ctx.stroke();
        }
        for (let y = 0; y < this.height; y += gridSize) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(this.width, y);
            ctx.stroke();
        }
    }

    // ── Animation Loop ──
    animate() {
        if (!this.running) return;

        this.ctx.clearRect(0, 0, this.width, this.height);

        this.frameCount++;

        // Matrix rain (every other frame for performance)
        if (this.frameCount % 2 === 0) {
            this.drawMatrix();
        }

        // Particles
        this.updateParticles();
        this.drawParticles();

        requestAnimationFrame(() => this.animate());
    }

    destroy() {
        this.running = false;
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    window.cyberBg = new CyberBackground('cyber-bg-canvas');
});
