document.addEventListener('DOMContentLoaded', () => {
    const loader = document.getElementById('loader');
    const contentArea = document.getElementById('content-area');
    const activeCount = document.getElementById('activeCount');
    const refreshBtn = document.getElementById('refreshBtn');
    
    const grids = {
        jobs: document.getElementById('jobs-grid'),
        funding: document.getElementById('funding-grid'),
        professors: document.getElementById('professors-grid'),
        papers: document.getElementById('papers-grid')
    };

    let allJobs = [];

    // Fetch and render jobs
    async function loadJobs() {
        try {
            loader.style.display = 'flex';
            contentArea.style.display = 'none';
            
            // Add cache-busting to always get the latest json
            const response = await fetch('jobs_database.json?t=' + new Date().getTime());
            if (!response.ok) {
                throw new Error('Could not fetch jobs database. Ensure opportunity_finder.py has run at least once.');
            }
            
            const data = await response.json();
            
            // Convert dictionary to array
            allJobs = Object.values(data);
            
            // Sort jobs, assuming newer ones are added later (we can just reverse to show latest first)
            allJobs.reverse();

            renderJobs();
            loader.style.display = 'none';
            contentArea.style.display = 'block';
        } catch (error) {
            console.error(error);
            loader.innerHTML = `
                <div style="text-align: center; padding: 3rem; color: #ef4444;">
                    <h3>⚠️ Error Loading Data</h3>
                    <p>${error.message}</p>
                    <p style="margin-top: 1rem; font-size: 0.9rem; color: #94a3b8;">
                        (Make sure you have run your Python script at least once to generate the jobs_database.json file)
                    </p>
                </div>
            `;
            activeCount.textContent = '0';
        }
    }

    function renderJobs() {
        Object.values(grids).forEach(grid => grid.innerHTML = '');
        activeCount.textContent = allJobs.length;

        allJobs.forEach((job, index) => {
            const card = document.createElement('div');
            card.className = 'job-card';
            card.style.animation = `float 0.5s ease forwards ${index * 0.05}s`;
            card.style.opacity = '0';
            
            // Add a simple fade in animation dynamically
            card.animate([
                { opacity: 0, transform: 'translateY(20px)' },
                { opacity: 1, transform: 'translateY(0)' }
            ], {
                duration: 500,
                delay: index * 50,
                fill: 'forwards',
                easing: 'ease-out'
            });

            // Make sure company is styled nicely
            const companyIcon = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2" ry="2"/><path d="M9 9h6"/><path d="M9 13h6"/><path d="M9 17h6"/></svg>`;

            let tagClass = 'source-default';
            let sourceName = job.source.toLowerCase();
            if (sourceName.includes('bd') || sourceName.includes('govt')) tagClass = 'source-reddit';
            else if (sourceName.includes('professors')) tagClass = 'source-reddit';
            else if (sourceName.includes('remotive')) tagClass = 'source-remotive';
            else if (sourceName.includes('weworkremotely')) tagClass = 'source-weworkremotely';
            else if (sourceName.includes('nsf')) tagClass = 'source-nsf';
            else if (sourceName.includes('ukri')) tagClass = 'source-ukri';
            else if (sourceName.includes('openaire')) tagClass = 'source-openaire';
            else if (sourceName.includes('openalex')) tagClass = 'source-openalex';
            else if (sourceName.includes('github')) tagClass = 'source-github';
            else if (sourceName.includes('arxiv')) tagClass = 'source-arxiv';

            let cardContent = '';
            
            if (sourceName.includes('professors')) {
                const emailIcon = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>`;
                let pureEmail = job.company.replace('Email: ', '');
                cardContent = `
                    <div>
                        <div class="tag-container">
                            <span class="job-source ${tagClass}">Research Lead</span>
                        </div>
                        <h3 class="job-title" style="color: #c4b5fd;">${job.title}</h3>
                        <div class="job-company" style="color: #e2e8f0; font-weight: 500;">
                            ${emailIcon} 
                            <a href="mailto:${pureEmail}" style="color: #93c5fd; text-decoration: none; margin-left: 5px;">${pureEmail}</a>
                        </div>
                    </div>
                    <div class="job-action">
                        <a href="${job.link}" target="_blank" rel="noopener noreferrer" class="apply-btn" style="background: rgba(139, 92, 246, 0.15); border-color: #8b5cf6;">Visit Lab Website</a>
                    </div>
                `;
            } else {
                cardContent = `
                    <div>
                        <div class="tag-container">
                            <span class="job-source ${tagClass}">${job.source}</span>
                        </div>
                        <h3 class="job-title">${job.title}</h3>
                        <div class="job-company">
                            ${companyIcon} ${job.company}
                        </div>
                    </div>
                    <div class="job-action">
                        <a href="${job.link}" target="_blank" rel="noopener noreferrer" class="apply-btn">View Opportunity</a>
                    </div>
                `;
            }
            
            card.innerHTML = cardContent;
            
            // Distribute into categories
            if (sourceName.includes('professors')) {
                grids.professors.appendChild(card);
            } else if (sourceName.includes('arxiv')) {
                grids.papers.appendChild(card);
            } else if (sourceName.includes('remotive') || sourceName.includes('wework') || sourceName.includes('bd') || sourceName.includes('govt')) {
                grids.jobs.appendChild(card);
            } else {
                grids.funding.appendChild(card);
            }
        });
        
        // Handle empty grids
        Object.values(grids).forEach(grid => {
            if (grid.children.length === 0) {
                grid.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; color: #94a3b8; padding: 2rem;">No data available right now.</div>`;
            }
        });
    }

    // Tab Navigation Logic
    const tabBtns = document.querySelectorAll('.filter-btn');
    const sections = document.querySelectorAll('.category-section');
    
    tabBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            // Remove active class from all buttons
            tabBtns.forEach(b => b.classList.remove('active'));
            // Add active class to clicked button
            e.target.classList.add('active');
            
            // Hide all sections
            sections.forEach(sec => sec.style.display = 'none');
            
            // Show target section
            const targetId = e.target.getAttribute('data-tab');
            document.getElementById(targetId).style.display = 'block';
        });
    });

    // Event Listeners
    refreshBtn.addEventListener('click', () => {
        // Rotate icon for feedback
        const svg = refreshBtn.querySelector('svg');
        svg.style.transition = 'transform 0.5s';
        svg.style.transform = 'rotate(360deg)';
        setTimeout(() => {
            svg.style.transition = 'none';
            svg.style.transform = 'rotate(0)';
        }, 500);
        
        loadJobs();
    });

    // Initial Load
    loadJobs();
});
