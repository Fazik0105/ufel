const burger = document.getElementById('hamburger');
const menu = document.getElementById('mobileMenu');

burger.addEventListener('click', e => {
    e.stopPropagation();
    menu.classList.toggle('active');
});

menu.addEventListener('click', e => {
    e.stopPropagation();
});


document.addEventListener('click', () => {
    menu.classList.remove('active');
});


menu.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => {
        menu.classList.remove('active');
    });
});
