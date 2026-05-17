export default function debug(ctx) {
  ctx.action("static.emphasize", {
    label: "Emphasize static shell",
    scope: "static_shell",
    group: "View",
  }, () => {
    document.querySelectorAll("span").forEach((el) => {
      el.style.transform = "translateY(-2px)";
      el.style.boxShadow = "0 10px 30px rgba(20, 184, 166, 0.25)";
      setTimeout(() => {
        el.style.transform = "";
        el.style.boxShadow = "";
      }, 900);
    });
  });
}
