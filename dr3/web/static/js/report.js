document.addEventListener('DOMContentLoaded', () => {
    const exportPdfBtn = document.getElementById('export-pdf');

    if (exportPdfBtn) {
        exportPdfBtn.addEventListener('click', generatePDFReport);
    }

    function generatePDFReport() {
        const element = document.getElementById('results-section');
        
        // We clone the section to avoid breaking the UI during generation
        const clonedElement = element.cloneNode(true);
        
        // Remove buttons and controls from the PDF
        const actions = clonedElement.querySelector('.section-actions');
        if (actions) actions.remove();
        
        const graphControls = clonedElement.querySelector('.graph-controls');
        if (graphControls) graphControls.remove();
        
        // Preserve the Cyber Intelligence theme (Dark Mode)
        clonedElement.style.padding = '20px';
        clonedElement.style.background = '#050505';
        
        // Inject a style fix for Arabic letter connection and RTL layout
        const styleFix = document.createElement('style');
        styleFix.innerHTML = `
            * { letter-spacing: normal !important; }
            .identity-meta-item, .tag, .platform-chip, .badge { display: inline-block; direction: rtl; unicode-bidi: embed; }
        `;
        clonedElement.appendChild(styleFix);

        const opt = {
            margin:       10,
            filename:     'DR3_Intelligence_Report_' + new Date().toISOString().slice(0, 10) + '.pdf',
            image:        { type: 'jpeg', quality: 0.98 },
            html2canvas:  { scale: 2, useCORS: true, letterRendering: true, backgroundColor: '#050505' },
            jsPDF:        { unit: 'mm', format: 'a4', orientation: 'portrait' }
        };

        // Adding Intelligence Agency Watermark or Header
        const header = document.createElement('div');
        header.innerHTML = `
            <div style="border-bottom: 2px solid #00d4ff; padding-bottom: 10px; margin-bottom: 20px; text-align: center;">
                <h1 style="color: #00d4ff; margin:0; font-family: 'JetBrains Mono', monospace;">DR3 DIGITAL INTELLIGENCE REPORT</h1>
                <p style="color: #6c757d; margin:0; font-size: 12px; font-family: 'Inter', sans-serif;">CONFIDENTIAL & PROPRIETARY — Generated on ${new Date().toLocaleString()}</p>
            </div>
        `;
        clonedElement.insertBefore(header, clonedElement.firstChild);

        html2pdf().set(opt).from(clonedElement).save().then(() => {
            console.log("PDF generated successfully");
        }).catch(err => {
            console.error("PDF Generation Error: ", err);
            alert("حدث خطأ أثناء توليد التقرير.");
        });
    }
});
