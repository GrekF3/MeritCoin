(function () {
	"use strict";

	const CLICK_THRESHOLD = 5;
	const LOGO_SELECTOR = ".brand-name, .nav-logo, .auth-logo, .student-brand";
	const MARK_ID = "project-mark-overlay";
	const STYLE_ID = "project-mark-style";
	const PEOPLE = ["Карелин Михаил", "Бусарев Дмитрий", "Абдуллоев Умеджон"];

	function injectStyle() {
		if (document.getElementById(STYLE_ID)) return;
		const style = document.createElement("style");
		style.id = STYLE_ID;
		style.textContent = `
			.project-mark[hidden] { display: none; }
			.project-mark {
				position: fixed;
				inset: 0;
				z-index: 9999;
				display: grid;
				place-items: center;
				padding: 1.25rem;
				background: rgba(1, 4, 12, 0.72);
				backdrop-filter: blur(18px);
			}
			.project-mark-card {
				width: min(100%, 23rem);
				border: 1px solid rgba(0, 200, 255, 0.28);
				border-radius: 0.5rem;
				background: linear-gradient(145deg, rgba(10, 14, 24, 0.96), rgba(4, 8, 16, 0.96));
				box-shadow: 0 1.4rem 4rem rgba(0, 0, 0, 0.42);
				color: #f3fbff;
				font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
				padding: 1.35rem;
			}
			.project-mark-kicker {
				margin: 0 0 0.85rem;
				color: rgba(243, 251, 255, 0.58);
				font-size: 0.74rem;
				letter-spacing: 0.08em;
				text-transform: uppercase;
			}
			.project-mark-list {
				display: grid;
				gap: 0.55rem;
				margin: 0;
				padding: 0;
				list-style: none;
			}
			.project-mark-list li {
				border-bottom: 1px solid rgba(243, 251, 255, 0.1);
				padding-bottom: 0.55rem;
				font-size: 1rem;
			}
			.project-mark-list li:last-child {
				border-bottom: 0;
				padding-bottom: 0;
			}
			.project-mark-close {
				width: 100%;
				margin-top: 1.1rem;
				border: 1px solid rgba(0, 200, 255, 0.34);
				border-radius: 0.45rem;
				background: rgba(0, 200, 255, 0.1);
				color: #f3fbff;
				cursor: pointer;
				font: inherit;
				padding: 0.72rem 0.9rem;
			}
			.project-mark-close:hover,
			.project-mark-close:focus-visible {
				background: rgba(0, 200, 255, 0.18);
				outline: none;
			}
		`;
		document.head.append(style);
	}

	function ensureOverlay() {
		let overlay = document.getElementById(MARK_ID);
		if (overlay) return overlay;

		injectStyle();
		overlay = document.createElement("div");
		overlay.id = MARK_ID;
		overlay.className = "project-mark";
		overlay.hidden = true;
		overlay.innerHTML = `
			<section class="project-mark-card" role="dialog" aria-modal="true" aria-labelledby="project-mark-title">
				<p class="project-mark-kicker" id="project-mark-title">Проект выполнен</p>
				<ul class="project-mark-list">
					${PEOPLE.map((name) => `<li>${name}</li>`).join("")}
				</ul>
				<button class="project-mark-close" type="button">Закрыть</button>
			</section>
		`;
		document.body.append(overlay);
		overlay.addEventListener("click", (event) => {
			if (event.target === overlay) closeOverlay();
		});
		overlay.querySelector(".project-mark-close")?.addEventListener("click", closeOverlay);
		return overlay;
	}

	function openOverlay() {
		const overlay = ensureOverlay();
		overlay.hidden = false;
		overlay.querySelector("button")?.focus();
	}

	function closeOverlay() {
		const overlay = document.getElementById(MARK_ID);
		if (overlay) overlay.hidden = true;
	}

	function initLogoTriggers() {
		document.querySelectorAll(LOGO_SELECTOR).forEach((logo) => {
			let count = 0;
			logo.addEventListener("click", () => {
				count += 1;
				if (count < CLICK_THRESHOLD) return;
				count = 0;
				openOverlay();
			});
		});
	}

	document.addEventListener("keydown", (event) => {
		if (event.key === "Escape") closeOverlay();
	});

	document.addEventListener("DOMContentLoaded", initLogoTriggers);
})();
