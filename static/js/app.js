document.querySelectorAll('.liga-tab').forEach(tab => {
  tab.addEventListener('click', function(e) {
    e.preventDefault();
    const url = this.href;
    fetch(url + '?partial=1')  // yoki alohida endpoint
      .then(res => res.json())
      .then(data => {
        document.querySelector('.tournaments-container').innerHTML = data.html;
        // active klassni yangilash
      });
  });
});