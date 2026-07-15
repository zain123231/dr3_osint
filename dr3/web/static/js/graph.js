/**
 * DR3 Intelligence Platform — Graph Visualization Engine
 * 
 * Professional intelligence graph powered by Cytoscape.js.
 * Features:
 *   - Confidence-colored nodes with neon glow
 *   - Animated edges showing relationship strength
 *   - Force-directed layout with concentric seed positioning
 *   - Node tap for details, double-tap for expansion
 *   - Image previews in nodes (when avatar available)
 *   - Platform icons and labels
 */

class GraphVisualization {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.cy = null;
        this.nodes = new Map();
        this.edges = new Map();
        
        if (this.container) {
            this.init();
        }
    }

    init() {
        this.cy = cytoscape({
            container: this.container,
            elements: [],
            style: [
                // ── Default Node ──
                {
                    selector: 'node',
                    style: {
                        'background-color': '#10161d',
                        'label': 'data(label)',
                        'color': '#8b9bb4',
                        'text-valign': 'bottom',
                        'text-halign': 'center',
                        'text-margin-y': 8,
                        'font-size': '11px',
                        'font-family': '"Share Tech Mono", monospace',
                        'border-width': 2,
                        'border-color': '#2a3547',
                        'width': 'data(size)',
                        'height': 'data(size)',
                        'text-max-width': '120px',
                        'text-wrap': 'ellipsis',
                        'overlay-padding': 6,
                        'transition-property': 'border-color, border-width, background-color',
                        'transition-duration': '0.3s',
                    }
                },
                // ── Seed Node ──
                {
                    selector: 'node.seed',
                    style: {
                        'border-color': '#ff3b3b',
                        'border-width': 4,
                        'background-color': '#1a0a0f',
                        'color': '#ff3b3b',
                        'font-weight': 'bold',
                        'font-size': '13px',
                        'text-outline-color': '#050505',
                        'text-outline-width': 2,
                        'shadow-blur': 20,
                        'shadow-color': 'rgba(255, 59, 59, 0.3)',
                        'shadow-opacity': 1,
                    }
                },
                // ── High Confidence Node ──
                {
                    selector: 'node.confidence-high',
                    style: {
                        'border-color': '#00ff66',
                        'border-width': 3,
                        'background-color': '#0a1a10',
                        'shadow-blur': 15,
                        'shadow-color': 'rgba(0, 255, 102, 0.25)',
                        'shadow-opacity': 1,
                        'color': '#00ff66',
                    }
                },
                // ── Medium Confidence Node ──
                {
                    selector: 'node.confidence-medium',
                    style: {
                        'border-color': '#00eaff',
                        'border-width': 2,
                        'background-color': '#0a1520',
                        'shadow-blur': 10,
                        'shadow-color': 'rgba(0, 234, 255, 0.2)',
                        'shadow-opacity': 1,
                        'color': '#00eaff',
                    }
                },
                // ── Low Confidence Node ──
                {
                    selector: 'node.confidence-low',
                    style: {
                        'border-color': '#ffb000',
                        'border-width': 2,
                        'background-color': '#1a150a',
                        'shadow-blur': 8,
                        'shadow-color': 'rgba(255, 176, 0, 0.15)',
                        'shadow-opacity': 1,
                        'color': '#ffb000',
                    }
                },
                // ── Node with avatar ──
                {
                    selector: 'node[avatarUrl]',
                    style: {
                        'background-image': 'data(avatarUrl)',
                        'background-fit': 'cover',
                        'background-clip': 'node',
                    }
                },
                // ── Node hover ──
                {
                    selector: 'node:active',
                    style: {
                        'overlay-color': '#00eaff',
                        'overlay-opacity': 0.15,
                    }
                },
                // ── Selected node ──
                {
                    selector: 'node:selected',
                    style: {
                        'border-color': '#b53cff',
                        'border-width': 4,
                        'shadow-blur': 25,
                        'shadow-color': 'rgba(181, 60, 255, 0.4)',
                        'shadow-opacity': 1,
                    }
                },
                // ── Default Edge ──
                {
                    selector: 'edge',
                    style: {
                        'width': 'data(width)',
                        'line-color': 'data(color)',
                        'curve-style': 'bezier',
                        'target-arrow-shape': 'triangle',
                        'target-arrow-color': 'data(color)',
                        'arrow-scale': 0.8,
                        'opacity': 0.6,
                        'transition-property': 'opacity, line-color',
                        'transition-duration': '0.3s',
                    }
                },
                // ── Edge hover ──
                {
                    selector: 'edge:active',
                    style: {
                        'opacity': 1,
                        'width': 3,
                        'overlay-color': '#00eaff',
                        'overlay-opacity': 0.1,
                    }
                },
                // ── Strong edge ──
                {
                    selector: 'edge.strong',
                    style: {
                        'line-style': 'solid',
                        'opacity': 0.8,
                    }
                },
                // ── Weak edge ──
                {
                    selector: 'edge.weak',
                    style: {
                        'line-style': 'dashed',
                        'opacity': 0.3,
                    }
                },
            ],
            layout: {
                name: 'concentric',
                animate: true,
                animationDuration: 800,
            },
            // Interaction
            minZoom: 0.2,
            maxZoom: 4,
            wheelSensitivity: 0.3,
        });

        // ── Event Listeners ──
        this.cy.on('tap', 'node', (evt) => {
            const nodeData = evt.target.data();
            this.showNodeDetails(nodeData);
        });

        this.cy.on('tap', 'edge', (evt) => {
            const edgeData = evt.target.data();
            this.showEdgeDetails(edgeData);
        });

        // Double tap for interactive expansion
        this.cy.on('dblclick dbltap', 'node', (evt) => {
            const nodeData = evt.target.data();
            if (window.expandNode && nodeData.raw && nodeData.raw.username) {
                window.expandNode(nodeData.raw.username);
            }
        });

        // Highlight connected elements on hover
        this.cy.on('mouseover', 'node', (evt) => {
            const node = evt.target;
            const neighborhood = node.neighborhood().add(node);
            this.cy.elements().not(neighborhood).style('opacity', 0.2);
            neighborhood.style('opacity', 1);
        });

        this.cy.on('mouseout', 'node', () => {
            this.cy.elements().style('opacity', '');
        });
    }

    updateGraph(graphData) {
        if (!this.cy || !graphData) return;

        const elements = [];

        // Add nodes
        if (graphData.nodes) {
            const nodesArray = Array.isArray(graphData.nodes) 
                ? graphData.nodes 
                : Object.values(graphData.nodes);

            nodesArray.forEach(node => {
                if (this.nodes.has(String(node.id))) return;
                
                const confidence = node.confidence || 0;
                let classes = [];
                
                if (node.is_seed) {
                    classes.push('seed');
                } else if (confidence >= 70) {
                    classes.push('confidence-high');
                } else if (confidence >= 40) {
                    classes.push('confidence-medium');
                } else {
                    classes.push('confidence-low');
                }

                const nodeData = {
                    id: String(node.id),
                    label: this.formatNodeLabel(node),
                    size: node.is_seed ? 50 : Math.max(20, Math.min(40, confidence / 2.5)),
                    raw: node,
                };

                // Add avatar if available
                if (node.avatar_url) {
                    nodeData.avatarUrl = node.avatar_url;
                }

                elements.push({
                    group: 'nodes',
                    data: nodeData,
                    classes: classes.join(' '),
                });
                this.nodes.set(String(node.id), true);
            });
        }

        // Add edges
        if (graphData.edges) {
            const edgesArray = Array.isArray(graphData.edges)
                ? graphData.edges
                : Object.values(graphData.edges);

            edgesArray.forEach(edge => {
                if (this.edges.has(String(edge.id))) return;
                if (!this.nodes.has(String(edge.source_id)) || !this.nodes.has(String(edge.target_id))) return;

                const strength = edge.strength || 0;
                let color = '#2a3547';
                let edgeClasses = [];

                if (strength >= 80) {
                    color = '#00ff66';
                    edgeClasses.push('strong');
                } else if (strength >= 50) {
                    color = '#00eaff';
                } else if (strength >= 30) {
                    color = '#ffb000';
                    edgeClasses.push('weak');
                } else {
                    color = '#ff3b3b';
                    edgeClasses.push('weak');
                }

                elements.push({
                    group: 'edges',
                    data: {
                        id: String(edge.id),
                        source: String(edge.source_id),
                        target: String(edge.target_id),
                        color: color,
                        width: Math.max(1, (strength / 100) * 4),
                        raw: edge,
                    },
                    classes: edgeClasses.join(' '),
                });
                this.edges.set(String(edge.id), true);
            });
        }

        if (elements.length > 0) {
            this.cy.add(elements);
            this.cy.resize();

            // Use concentric layout: seed in center, high confidence inner ring
            this.cy.layout({
                name: 'concentric',
                animate: true,
                animationDuration: 1000,
                animationEasing: 'ease-out',
                fit: true,
                padding: 40,
                concentric: (node) => {
                    const data = node.data('raw');
                    if (!data) return 0;
                    if (data.is_seed) return 100;
                    return data.confidence || 0;
                },
                levelWidth: () => 25,
                minNodeSpacing: 30,
            }).run();
        }
    }

    formatNodeLabel(node) {
        const platform = node.platform || '?';
        const username = node.username || '';
        
        if (node.is_seed) {
            return `🎯 ${platform}\n@${username}`;
        }
        
        const conf = Math.round(node.confidence || 0);
        return `${platform}\n@${username}\n${conf}%`;
    }

    clear() {
        if (this.cy) {
            this.cy.elements().remove();
            this.nodes.clear();
            this.edges.clear();
        }
    }

    showNodeDetails(nodeData) {
        // Dispatch event for external handlers
        window.dispatchEvent(new CustomEvent('dr3-node-selected', { detail: nodeData.raw }));
        
        // Log to terminal if available
        if (window.terminalLog && nodeData.raw) {
            const n = nodeData.raw;
            window.terminalLog(`Node: ${n.platform} @${n.username} (${Math.round(n.confidence || 0)}%)`, 'info');
        }
    }

    showEdgeDetails(edgeData) {
        window.dispatchEvent(new CustomEvent('dr3-edge-selected', { detail: edgeData.raw }));
    }

    // Public API for external control
    zoomIn()  { if (this.cy) this.cy.zoom(this.cy.zoom() * 1.3); }
    zoomOut() { if (this.cy) this.cy.zoom(this.cy.zoom() / 1.3); }
    fit()     { if (this.cy) this.cy.fit(undefined, 40); }
    center()  { if (this.cy) this.cy.center(); }
}

// Global instance placeholder
window.graphVis = null;
