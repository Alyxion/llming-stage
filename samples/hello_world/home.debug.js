export default function debug(ctx) {
  ctx.action("hello.highlight", {
    label: "Highlight greeting",
    scope: "hello_world",
    group: "View",
  }, () => {
    const title = document.querySelector("h1, .text-h2, main div");
    if (title) {
      title.style.transition = "filter 150ms ease, transform 150ms ease";
      title.style.filter = "drop-shadow(0 0 18px rgba(34, 211, 238, 0.8))";
      title.style.transform = "scale(1.03)";
      setTimeout(() => { title.style.transform = ""; }, 450);
    }
  });
}
