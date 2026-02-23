document.addEventListener('DOMContentLoaded', () => {
    const openBtn = document.querySelector('.create-turnir');
    const modal = document.getElementById('createTournirModal');
    const closeBtn = modal.querySelector('.modal-close');

    openBtn.addEventListener('click', (e) => {
        e.preventDefault();
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    });

    closeBtn.addEventListener('click', () => {
        modal.classList.remove('active');
        document.body.style.overflow = '';
    });
});
