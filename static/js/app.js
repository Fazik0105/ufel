document.querySelectorAll('.liga-tab').forEach(tab => {
    tab.addEventListener('click', function(e) {
        e.preventDefault();
        
        // Aktiv klassni o'zgartirish
        document.querySelectorAll('.liga-tab').forEach(t => t.classList.remove('active'));
        this.classList.add('active');
        
        const champId = this.getAttribute('data-liga');
        
        // Yuklanish indikatori (ixtiyoriy)
        document.getElementById('tournament-table-body').style.opacity = '0.5';

        fetch(`/app/get-championship-data/${champId}/`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Jadvalni yangilash
                    document.getElementById('tournament-table-body').innerHTML = data.table_html;
                    // Sarlavhani yangilash
                    document.getElementById('active-champ-name').innerText = data.champ_name;
                    // Admin panelni yangilash (agar bo'lsa)
                    const adminWrapper = document.getElementById('admin-section-wrapper');
                    if (adminWrapper) {
                        adminWrapper.innerHTML = data.admin_html;
                    }
                }
            })
            .catch(error => console.error('Error:', error))
            .finally(() => {
                document.getElementById('tournament-table-body').style.opacity = '1';
            });
    });
});