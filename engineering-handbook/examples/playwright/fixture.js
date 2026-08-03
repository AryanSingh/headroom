const state = document.querySelector("#state");
const recovery = document.querySelector("#recovery");

document.querySelector("#simulate").addEventListener("click", () => {
  state.textContent = "Evidence check interrupted.";
  recovery.hidden = false;
});

document.querySelector("#retry").addEventListener("click", () => {
  state.textContent = "Evidence is ready for review.";
  recovery.hidden = true;
});
