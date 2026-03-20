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

// // Playoff bracket interaktivligi
// function initPlayoffBracket() {
//     const bracketMatches = document.querySelectorAll('.bracket-match');
    
//     bracketMatches.forEach(match => {
//         match.addEventListener('click', function(e) {
//             // Agar admin bo'lsa, match tahrirlash modalini ochish
//             if (document.body.classList.contains('user-admin')) {
//                 const matchId = this.dataset.matchId;
//                 if (matchId) {
//                     openMatchEditor(matchId);
//                 }
//             }
//         });
        
//         // Hover effekti
//         match.addEventListener('mouseenter', function() {
//             const winnerTeam = this.querySelector('.match-team.winner');
//             if (winnerTeam) {
//                 winnerTeam.style.transform = 'scale(1.02)';
//             }
//         });
        
//         match.addEventListener('mouseleave', function() {
//             const winnerTeam = this.querySelector('.match-team.winner');
//             if (winnerTeam) {
//                 winnerTeam.style.transform = 'scale(1)';
//             }
//         });
//     });
// }

// Match tahrirlash modalini ochish (admin uchun)
function openMatchEditor(matchId) {
    // Bu funksiyani admin panelga moslab yozish mumkin
    const modal = document.createElement('div');
    modal.className = 'match-editor-modal';
    modal.innerHTML = `
        <div class="modal-backdrop"></div>
        <div class="modal-content">
            <h3>O'yin natijasini tahrirlash</h3>
            <form id="match-edit-form-${matchId}">
                <input type="number" name="home_score" placeholder="Home score">
                <input type="number" name="away_score" placeholder="Away score">
                <button type="submit">Saqlash</button>
            </form>
        </div>
    `;
    document.body.appendChild(modal);
    
    // Form submit
    document.getElementById(`match-edit-form-${matchId}`).addEventListener('submit', function(e) {
        e.preventDefault();
        // AJAX orqali yuborish
        // ...
    });
}

// Sahifa yuklanganda ishga tushirish
document.addEventListener('DOMContentLoaded', function() {
    if (document.querySelector('.bracket-wrapper')) {
        initPlayoffBracket();
    }
});