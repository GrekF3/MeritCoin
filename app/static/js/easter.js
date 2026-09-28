(function () {
	"use strict";

	const VIDEO_SRC = "/static/img/easter/tractor.mp4";
	const BOOM_DELAY_MS = 950;

	function ensureOverlay() {
		let overlay = document.querySelector("[data-easter-overlay]");
		if (overlay) return overlay;

		overlay = document.createElement("div");
		overlay.className = "easter-overlay";
		overlay.dataset.easterOverlay = "true";
		overlay.hidden = true;
		overlay.innerHTML = `
			<div class="easter-flash" aria-hidden="true"></div>
			<video class="easter-video" src="${VIDEO_SRC}" preload="auto" playsinline loop></video>
			<button class="easter-close" type="button" aria-label="Закрыть">Закрыть</button>
		`;
		document.body.append(overlay);

		overlay.querySelector(".easter-close")?.addEventListener("click", () => {
			const video = overlay.querySelector("video");
			video?.pause();
			overlay.hidden = true;
			document.documentElement.classList.remove("easter-boom", "easter-priming");
		});

		return overlay;
	}

	function showBlast() {
		let blast = document.querySelector("[data-easter-blast]");
		if (!blast) {
			blast = document.createElement("div");
			blast.className = "easter-blast";
			blast.dataset.easterBlast = "true";
			blast.innerHTML = `
				<span class="easter-blast-ring"></span>
				<span class="easter-blast-core"></span>
				<span class="easter-blast-noise"></span>
			`;
			document.body.append(blast);
		}

		blast.hidden = false;
		blast.classList.remove("is-active");
		window.requestAnimationFrame(() => blast.classList.add("is-active"));
		return blast;
	}

	function launchEaster() {
		const overlay = ensureOverlay();
		const video = overlay.querySelector("video");
		const blast = showBlast();
		document.documentElement.classList.add("easter-boom", "easter-priming");
		overlay.hidden = true;
		window.setTimeout(() => {
			blast.hidden = true;
			document.documentElement.classList.remove("easter-priming");
			overlay.hidden = false;
			if (video) {
				video.currentTime = 0;
				video.play().catch(() => {
					video.muted = true;
					video.play().catch(() => {});
				});
			}
		}, BOOM_DELAY_MS);
	}

	function initLoginTrigger() {
		const form = document.querySelector(".auth-form");
		if (!form) return;

		form.addEventListener("submit", (event) => {
			const username = form.querySelector('input[name="username"]')?.value.trim().toLowerCase();
			const password = form.querySelector('input[name="password"]')?.value.trim().toLowerCase();
			if (username === "tractor" && password === "tractor") {
				event.preventDefault();
				launchEaster();
			}
		});
	}

	function initSettingsTrigger() {
		const tabs = Array.from(document.querySelectorAll("[data-tab]"));
		if (!tabs.length) return;

		let settingsClicks = 0;
		tabs.forEach((tab) => {
			tab.addEventListener("click", () => {
				if (tab.dataset.tab === "settings") {
					settingsClicks += 1;
					if (settingsClicks >= 5) {
						settingsClicks = 0;
						launchEaster();
					}
					return;
				}
				settingsClicks = 0;
			});
		});
	}

	document.addEventListener("DOMContentLoaded", () => {
		initLoginTrigger();
		initSettingsTrigger();
	});
})();
