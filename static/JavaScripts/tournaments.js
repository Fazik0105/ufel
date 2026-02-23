document.addEventListener('DOMContentLoaded', function() {
    const tabs = document.querySelectorAll('.liga-tab');
    const tableBody = document.getElementById('tournament-table-body');
    const adminWrapper = document.getElementById('admin-section-wrapper');
    const tableBadge = document.querySelector('.table-badge');

    tabs.forEach(tab => {
        tab.addEventListener('click', function(e) {
            e.preventDefault();

            // 1. Aktiv klassni yangilash
            tabs.forEach(t => t.classList.remove('active'));
            this.classList.add('active');
            
            // 2. Yuklanish effektini berish (xiralashtirish)
            tableBody.style.opacity = '0.4';
            if(adminWrapper) adminWrapper.style.opacity = '0.4';

            const fetchUrl = this.getAttribute('data-url'); 

            fetch(fetchUrl, {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => {
                if (!response.ok) throw new Error('Tarmoq xatosi');
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    // Ma'lumotlarni yangilash
                    tableBody.innerHTML = data.table_html;
                    if(tableBadge) tableBadge.innerText = data.champ_name;
                    if(adminWrapper) adminWrapper.innerHTML = data.admin_html;
                    
                    // Sarlavhani ham yangilash (agar u mavjud bo'lsa)
                    const titleElem = document.getElementById('active-champ-name');
                    if(titleElem) titleElem.innerText = data.champ_name;
                }
            })
            .catch(error => console.error('Xatolik:', error))
            .finally(() => {
                // 3. HAR QANDAY HOLATDA xiralikni qaytarish
                tableBody.style.opacity = '1';
                if(adminWrapper) adminWrapper.style.opacity = '1';
            });
        });
    });
});