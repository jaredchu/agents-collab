// Progressive enhancement only: adds copy buttons to code blocks.
// Pages are complete without this script.
(function () {
  "use strict";
  if (!navigator.clipboard || !window.isSecureContext) return;

  var status = document.createElement("p");
  status.className = "visually-hidden";
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  document.body.appendChild(status);

  var blocks = document.querySelectorAll(".code-block");
  Array.prototype.forEach.call(blocks, function (block) {
    var code = block.querySelector("pre code");
    if (!code) return;
    var labelEl = block.querySelector(".code-label");
    var label = labelEl ? labelEl.textContent.trim() : "code";
    var button = document.createElement("button");
    button.type = "button";
    button.className = "copy-button";
    button.textContent = "Copy";
    button.setAttribute("aria-label", "Copy " + label);
    button.addEventListener("click", function () {
      navigator.clipboard.writeText(code.textContent).then(function () {
        button.textContent = "Copied";
        status.textContent = "Copied " + label + " to the clipboard.";
        window.setTimeout(function () { button.textContent = "Copy"; }, 2000);
      }, function () {
        status.textContent = "Copy failed. Select the text and copy it manually.";
      });
    });
    block.appendChild(button);
  });
})();
