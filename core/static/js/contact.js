document.addEventListener("DOMContentLoaded", function () {
  const inputs = document.querySelectorAll(".form-control");
  inputs.forEach((input) => {
    input.addEventListener("input", () => {
      const error = input.parentNode.querySelector(".text-danger.small");
      if (error) error.remove();
    });
  });
});
