// Demo-page chrome only: the encounter form never submits, and "Clear form"
// lets the same page be tried again without a reload.
(function () {
  var form = document.getElementById("encounter");
  form.addEventListener("submit", function (event) { event.preventDefault(); });

  document.getElementById("clear").addEventListener("click", function () {
    Array.prototype.forEach.call(form.querySelectorAll("input, textarea"), function (field) {
      field.value = "";
    });
  });
})();
