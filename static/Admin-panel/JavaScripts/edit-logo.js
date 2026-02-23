document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('editLogoBtn');
    const input = document.getElementById('logoInput');

    btn.addEventListener('click', (e) => {
        e.preventDefault();
        input.click(); // file tanlash oynasini ochadi
    });

    input.addEventListener('change', () => {
        const file = input.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = () => {
            btn.style.backgroundImage = `url(${reader.result})`;
            btn.style.backgroundSize = 'cover';
            btn.style.backgroundPosition = 'center';
            btn.textContent = ''; // + ni olib tashlaydi
        };
        reader.readAsDataURL(file);
    });
});
