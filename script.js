document.addEventListener('DOMContentLoaded', () => {
    const jobBoard = document.getElementById('job-board');
    const activeCount = document.getElementById('activeCount');
    const filterBtns = document.querySelectorAll('.filter-btn');
    const refreshBtn = document.getElementById('refreshBtn');

    let allJobs = [];

    // Fetch and render jobs
    async function loadJobs() {
        try {
            jobBoard.innerHTML = `
                <div class="loader-container">
                    <div class="spinner"></div>
                    <p>Loading opportunities...</p>
                </div>
            `;
            
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

            renderJobs('all');
        } catch (error) {
            console.error(error);
            jobBoard.innerHTML = `
                <div style="grid-column: 1 / -1; text-align: center; padding: 3rem; color: #ef4444;">
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

    function renderJobs(filter) {
        jobBoard.innerHTML = '';
        
        let filteredJobs = allJobs;
        if (filter !== 'all') {
            filteredJobs = allJobs.filter(job => {
                let src = job.source.toLowerCase();
                let f = filter.toLowerCase();
                if (f === 'bd govt' && (src.includes('ict') || src.includes('bcc') || src.includes('govt'))) return true;
                return src.includes(f);
            });
        }

        activeCount.textContent = filteredJobs.length;

        if (filteredJobs.length === 0) {
            jobBoard.innerHTML = `
                <div style="grid-column: 1 / -1; text-align: center; padding: 3rem; color: #94a3b8;">
                    <h3>No opportunities found for this filter.</h3>
                    <p>Check back later!</p>
                </div>
            `;
            return;
        }

        filteredJobs.forEach((job, index) => {
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
            if (sourceName.includes('bd') || sourceName.includes('govt')) tagClass = 'source-reddit'; // Reuse red/orange styling
            else if (sourceName.includes('professors')) tagClass = 'source-reddit'; // Reuse red/orange styling
            else if (sourceName.includes('remotive')) tagClass = 'source-remotive';
            else if (sourceName.includes('weworkremotely')) tagClass = 'source-weworkremotely';

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
            jobBoard.appendChild(card);
        });
    }

    // Event Listeners
    filterBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            filterBtns.forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            renderJobs(e.target.getAttribute('data-filter'));
        });
    });

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
