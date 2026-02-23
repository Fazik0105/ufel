document.addEventListener('DOMContentLoaded', () => {
  const modal = document.getElementById('deleteTournirModal');
  if (!modal) return;

  const closeBtn = modal.querySelector('.modal-close');
  const backdrop = modal.querySelector('.delete-tournir-backdrop');
  const cancelBtn = document.getElementById('deleteCancelBtn');
  const confirmBtn = document.getElementById('deleteConfirmBtn');

  // DELETE tugmasi bosilganda modal ochilsin
  document.addEventListener('click', (e) => {
    const delBtn = e.target.closest('.delete-tournir');
    if (delBtn) {
      e.preventDefault();
      openModal();
    }
  });

  // Yopishlar
  closeBtn?.addEventListener('click', closeModal);
  backdrop?.addEventListener('click', closeModal);

  cancelBtn?.addEventListener('click', (e) => {
    e.preventDefault();
    closeModal();
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal.classList.contains('active')) closeModal();
  });

  confirmBtn?.addEventListener('click', (e) => {
    e.preventDefault();
    // TODO: real delete shu yerda
    closeModal();
  });

  function openModal() {
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
  }

  function closeModal() {
    modal.classList.remove('active');
    document.body.style.overflow = '';
  }
});
