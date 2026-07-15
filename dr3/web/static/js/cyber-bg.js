/**
 * DR3 Intelligence Platform — Cyber Background Engine v2.0
 * 
 * Multi-layered animated cyber environment:
 * Layer 0: Perspective grid
 * Layer 1: Matrix rain (green falling characters)
 * Layer 2: Floating hex values
 * Layer 3: Network constellation
 * Layer 4: Scan lines + CRT effect
 * Layer 5: Ambient glow fog
 */

(function() {
    'use strict';

    const canvas = document.getElementById('cyber-bg-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    let W, H;
    const DPR = Math.min(window.devicePixelRatio || 1, 2);

    function resize() {
        W = window.innerWidth;
        H = window.innerHeight;
        canvas.width = W * DPR;
        canvas.height = H * DPR;
        canvas.style.width = W + 'px';
        canvas.style.height = H + 'px';
        ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
        initMatrix();
    }

    // ═══════════════════════════════════════════════
    // MATRIX RAIN
    // ═══════════════════════════════════════════════
    const MATRIX_CHARS = 'アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン0123456789ABCDEF:.;+=*^%$#@!~<>{}[]|/\\';
    const FONT_SIZE = 14;
    let columns = 0;
    let drops = [];

    function initMatrix() {
        columns = Math.floor(W / FONT_SIZE);
        drops = [];
        for (let i = 0; i < columns; i++) {
            drops[i] = Math.random() * -100;
        }
    }

    function drawMatrixRain() {
        // Fade effect
        ctx.fillStyle = 'rgba(4, 4, 4, 0.06)';
        ctx.fillRect(0, 0, W, H);

        for (let i = 0; i < columns; i++) {
            // Only render ~40% of columns for performance + sparser look
            if (i % 3 !== 0 && i % 5 !== 0) continue;
            
            const char = MATRIX_CHARS[Math.floor(Math.random() * MATRIX_CHARS.length)];
            const x = i * FONT_SIZE;
            const y = drops[i] * FONT_SIZE;

            // Head character — bright green
            ctx.font = `${FONT_SIZE}px 'JetBrains Mono', monospace`;
            ctx.fillStyle = '#00ff66';
            ctx.globalAlpha = 0.9;
            ctx.fillText(char, x, y);

            // Trail characters — dimmer
            ctx.globalAlpha = 0.15;
            ctx.fillStyle = '#00ff66';
            const trailChar = MATRIX_CHARS[Math.floor(Math.random() * MATRIX_CHARS.length)];
            ctx.fillText(trailChar, x, y - FONT_SIZE);
            ctx.globalAlpha = 0.07;
            ctx.fillText(trailChar, x, y - FONT_SIZE * 2);

            ctx.globalAlpha = 1;

            if (y > H && Math.random() > 0.975) {
                drops[i] = 0;
            }
            drops[i] += 0.5 + Math.random() * 0.3;
        }
    }

    // ═══════════════════════════════════════════════
    // GRID OVERLAY
    // ═══════════════════════════════════════════════
    function drawGrid() {
        const spacing = 60;
        ctx.strokeStyle = 'rgba(0, 255, 102, 0.03)';
        ctx.lineWidth = 0.5;
        ctx.beginPath();
        // Vertical lines
        for (let x = 0; x < W; x += spacing) {
            ctx.moveTo(x, 0);
            ctx.lineTo(x, H);
        }
        // Horizontal lines
        for (let y = 0; y < H; y += spacing) {
            ctx.moveTo(0, y);
            ctx.lineTo(W, y);
        }
        ctx.stroke();
    }

    // ═══════════════════════════════════════════════
    // FLOATING HEX VALUES
    // ═══════════════════════════════════════════════
    const hexParticles = [];
    const MAX_HEX = 15;

    function initHex() {
        for (let i = 0; i < MAX_HEX; i++) {
            hexParticles.push(createHexParticle());
        }
    }

    function createHexParticle() {
        const hexVal = '0x' + Math.floor(Math.random() * 0xFFFFFF).toString(16).toUpperCase().padStart(6, '0');
        return {
            x: Math.random() * W,
            y: Math.random() * H,
            text: hexVal,
            alpha: 0,
            alphaDir: 0.002 + Math.random() * 0.005,
            maxAlpha: 0.08 + Math.random() * 0.12,
            speed: 0.1 + Math.random() * 0.2,
        };
    }

    function drawHex() {
        ctx.font = '11px "JetBrains Mono", monospace';
        for (let p of hexParticles) {
            p.alpha += p.alphaDir;
            p.y -= p.speed;
            if (p.alpha >= p.maxAlpha) p.alphaDir = -Math.abs(p.alphaDir);
            if (p.alpha <= 0 || p.y < -20) {
                Object.assign(p, createHexParticle());
                p.y = H + 20;
                p.alpha = 0;
                p.alphaDir = Math.abs(p.alphaDir);
            }
            ctx.fillStyle = '#00ff66';
            ctx.globalAlpha = p.alpha;
            ctx.fillText(p.text, p.x, p.y);
        }
        ctx.globalAlpha = 1;
    }

    // ═══════════════════════════════════════════════
    // NETWORK CONSTELLATION
    // ═══════════════════════════════════════════════
    const netNodes = [];
    const MAX_NODES = 25;

    function initNetwork() {
        for (let i = 0; i < MAX_NODES; i++) {
            netNodes.push({
                x: Math.random() * W,
                y: Math.random() * H,
                vx: (Math.random() - 0.5) * 0.3,
                vy: (Math.random() - 0.5) * 0.3,
                r: 1 + Math.random() * 1.5,
                pulse: Math.random() * Math.PI * 2,
            });
        }
    }

    function drawNetwork() {
        const connDist = 180;
        // Draw connections
        ctx.lineWidth = 0.5;
        for (let i = 0; i < netNodes.length; i++) {
            for (let j = i + 1; j < netNodes.length; j++) {
                const dx = netNodes[i].x - netNodes[j].x;
                const dy = netNodes[i].y - netNodes[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < connDist) {
                    const alpha = (1 - dist / connDist) * 0.08;
                    ctx.strokeStyle = `rgba(0, 255, 102, ${alpha})`;
                    ctx.beginPath();
                    ctx.moveTo(netNodes[i].x, netNodes[i].y);
                    ctx.lineTo(netNodes[j].x, netNodes[j].y);
                    ctx.stroke();
                }
            }
        }

        // Draw nodes
        for (let n of netNodes) {
            n.pulse += 0.02;
            n.x += n.vx;
            n.y += n.vy;
            if (n.x < 0 || n.x > W) n.vx *= -1;
            if (n.y < 0 || n.y > H) n.vy *= -1;

            const glow = 0.3 + Math.sin(n.pulse) * 0.2;
            ctx.fillStyle = `rgba(0, 255, 102, ${glow})`;
            ctx.beginPath();
            ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
            ctx.fill();

            // Glow ring
            ctx.strokeStyle = `rgba(0, 255, 102, ${glow * 0.3})`;
            ctx.lineWidth = 0.5;
            ctx.beginPath();
            ctx.arc(n.x, n.y, n.r + 3, 0, Math.PI * 2);
            ctx.stroke();
        }
    }

    // ═══════════════════════════════════════════════
    // BINARY STREAMS (horizontal)
    // ═══════════════════════════════════════════════
    const binaryStreams = [];
    const MAX_STREAMS = 6;

    function initBinary() {
        for (let i = 0; i < MAX_STREAMS; i++) {
            binaryStreams.push({
                y: Math.random() * H,
                x: -200 - Math.random() * 500,
                speed: 0.3 + Math.random() * 0.8,
                text: Array.from({length: 40}, () => Math.random() > 0.5 ? '1' : '0').join(' '),
                alpha: 0.03 + Math.random() * 0.05,
            });
        }
    }

    function drawBinary() {
        ctx.font = '10px "JetBrains Mono", monospace';
        for (let s of binaryStreams) {
            s.x += s.speed;
            if (s.x > W + 200) {
                s.x = -600;
                s.y = Math.random() * H;
                s.text = Array.from({length: 40}, () => Math.random() > 0.5 ? '1' : '0').join(' ');
            }
            ctx.fillStyle = '#00ff66';
            ctx.globalAlpha = s.alpha;
            ctx.fillText(s.text, s.x, s.y);
        }
        ctx.globalAlpha = 1;
    }

    // ═══════════════════════════════════════════════
    // SCAN LINES
    // ═══════════════════════════════════════════════
    let scanY = 0;

    function drawScanLines() {
        // Static scan lines
        ctx.fillStyle = 'rgba(0, 255, 102, 0.008)';
        for (let y = 0; y < H; y += 3) {
            ctx.fillRect(0, y, W, 1);
        }

        // Moving scan line
        scanY = (scanY + 0.8) % H;
        const gradient = ctx.createLinearGradient(0, scanY - 30, 0, scanY + 30);
        gradient.addColorStop(0, 'rgba(0, 255, 102, 0)');
        gradient.addColorStop(0.5, 'rgba(0, 255, 102, 0.04)');
        gradient.addColorStop(1, 'rgba(0, 255, 102, 0)');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, scanY - 30, W, 60);
    }

    // ═══════════════════════════════════════════════
    // AMBIENT GLOW
    // ═══════════════════════════════════════════════
    let glowPhase = 0;

    function drawGlow() {
        glowPhase += 0.005;
        const intensity = 0.03 + Math.sin(glowPhase) * 0.015;
        
        // Center glow
        const grd = ctx.createRadialGradient(W / 2, H / 2, 0, W / 2, H / 2, W * 0.6);
        grd.addColorStop(0, `rgba(0, 255, 102, ${intensity})`);
        grd.addColorStop(1, 'rgba(0, 0, 0, 0)');
        ctx.fillStyle = grd;
        ctx.fillRect(0, 0, W, H);

        // Corner vignette
        const vignette = ctx.createRadialGradient(W / 2, H / 2, H * 0.3, W / 2, H / 2, W * 0.8);
        vignette.addColorStop(0, 'rgba(0, 0, 0, 0)');
        vignette.addColorStop(1, 'rgba(0, 0, 0, 0.4)');
        ctx.fillStyle = vignette;
        ctx.fillRect(0, 0, W, H);
    }

    // ═══════════════════════════════════════════════
    // MAIN LOOP
    // ═══════════════════════════════════════════════
    let frame = 0;

    function animate() {
        frame++;

        // Base clear — very dark with slight persistence
        if (frame % 2 === 0) {
            ctx.fillStyle = 'rgba(4, 4, 4, 0.15)';
            ctx.fillRect(0, 0, W, H);
        }

        // Layer 0: Grid (every 3rd frame)
        if (frame % 3 === 0) drawGrid();

        // Layer 1: Matrix rain (every frame)
        drawMatrixRain();

        // Layer 2: Binary streams (every frame)
        drawBinary();

        // Layer 3: Floating hex (every 2nd frame)
        if (frame % 2 === 0) drawHex();

        // Layer 4: Network constellation (every 2nd frame)
        if (frame % 2 === 0) drawNetwork();

        // Layer 5: Scan lines (every frame)
        drawScanLines();

        // Layer 6: Ambient glow (every 4th frame)
        if (frame % 4 === 0) drawGlow();

        requestAnimationFrame(animate);
    }

    // ═══════════════════════════════════════════════
    // INIT
    // ═══════════════════════════════════════════════
    function init() {
        resize();
        initHex();
        initNetwork();
        initBinary();

        // Initial fill
        ctx.fillStyle = '#040404';
        ctx.fillRect(0, 0, W, H);

        animate();
    }

    window.addEventListener('resize', resize);
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
