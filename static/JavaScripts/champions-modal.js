const modal = document.getElementById("modal");
const closeBtn = modal.querySelector(".modal-close");

function openModal() {
  modal.classList.add("active");
  document.body.classList.add("modal-open");
}

function closeModal() {
  modal.classList.remove("active");
  document.body.classList.remove("modal-open");
}

/* X icon bosilganda yopish */
closeBtn.addEventListener("click", closeModal);

/* backdrop bosilganda yopish */
modal.addEventListener("click", (e) => {
  if (e.target.classList.contains("modal-backdrop")) {
    closeModal();
  }
});

/* ESC */
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeModal();
});
