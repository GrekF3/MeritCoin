(function () {
	"use strict";

	function initIcons() {
		if (window.lucide && typeof window.lucide.createIcons === "function") {
			window.lucide.createIcons({
				attrs: {
					"stroke-width": 2,
					"aria-hidden": "true",
				},
			});
		}
	}

	function initCanvas() {
		const canvas = document.getElementById("student-neural-canvas");
		if (!canvas) return;

		const ctx = canvas.getContext("2d");
		const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
		let width = 0;
		let height = 0;
		let ratio = 1;
		let nodes = [];
		let frame = 0;

		function resize() {
			width = window.innerWidth;
			height = window.innerHeight;
			ratio = Math.min(window.devicePixelRatio || 1, 2);
			canvas.width = Math.floor(width * ratio);
			canvas.height = Math.floor(height * ratio);
			canvas.style.width = `${width}px`;
			canvas.style.height = `${height}px`;
			ctx.setTransform(ratio, 0, 0, ratio, 0, 0);

			const count = Math.max(34, Math.min(72, Math.round((width * height) / 19000)));
			nodes = Array.from({ length: count }, (_, index) => ({
				x: Math.random() * width,
				y: Math.random() * height,
				base: 28 + Math.random() * 96,
				speed: 0.35 + Math.random() * 0.7,
				phase: Math.random() * Math.PI * 2,
				size: 1.4 + Math.random() * 2.5,
				type: index % 5 === 0 ? "coin" : "node",
			}));
		}

		function drawCoin(node, alpha) {
			ctx.beginPath();
			ctx.arc(node.x, node.y, node.size * 2.1, 0, Math.PI * 2);
			ctx.strokeStyle = `rgba(0, 200, 255, ${alpha})`;
			ctx.lineWidth = 1;
			ctx.stroke();

			ctx.beginPath();
			ctx.arc(node.x, node.y, node.size * 0.9, 0, Math.PI * 2);
			ctx.fillStyle = `rgba(255, 0, 92, ${alpha * 0.72})`;
			ctx.fill();
		}

		function draw() {
			frame += reduceMotion ? 0.003 : 0.011;
			ctx.clearRect(0, 0, width, height);

			nodes.forEach((node, index) => {
				const drift = frame * node.speed + node.phase;
				if (!reduceMotion) {
					node.x += Math.cos(drift) * 0.18;
					node.y += Math.sin(drift * 0.8) * 0.18;
				}

				if (node.x < -20) node.x = width + 20;
				if (node.x > width + 20) node.x = -20;
				if (node.y < -20) node.y = height + 20;
				if (node.y > height + 20) node.y = -20;

				for (let j = index + 1; j < nodes.length; j += 1) {
					const other = nodes[j];
					const dx = node.x - other.x;
					const dy = node.y - other.y;
					const dist = Math.sqrt(dx * dx + dy * dy);
					if (dist < node.base) {
						const alpha = (1 - dist / node.base) * 0.13;
						ctx.beginPath();
						ctx.moveTo(node.x, node.y);
						ctx.lineTo(other.x, other.y);
						ctx.strokeStyle = `rgba(0, 200, 255, ${alpha})`;
						ctx.lineWidth = 1;
						ctx.stroke();
					}
				}

				const alpha = 0.18 + Math.sin(frame + node.phase) * 0.08;
				if (node.type === "coin") {
					drawCoin(node, alpha);
				} else {
					ctx.beginPath();
					ctx.arc(node.x, node.y, node.size, 0, Math.PI * 2);
					ctx.fillStyle = `rgba(243, 251, 255, ${alpha})`;
					ctx.fill();
				}
			});

			window.requestAnimationFrame(draw);
		}

		resize();
		draw();
		window.addEventListener("resize", resize);
	}

	function initTransferMath() {
		const form = document.querySelector(".transfer-form");
		if (!form) return;

		const amount = form.querySelector('input[name="amount"]');
		const fee = form.querySelector("[data-transfer-fee]");
		const net = form.querySelector("[data-transfer-net]");
		if (!amount || !fee || !net) return;

		function update() {
			const value = Math.max(0, Number.parseFloat(amount.value || "0") || 0);
			const feePercent = Math.max(0, Number.parseFloat(form.dataset.feePercent || "1") || 0);
			const computedFee = value > 0 && feePercent > 0 ? Math.max(0.01, Math.round(value * feePercent) / 100) : 0;
			fee.textContent = computedFee.toFixed(2);
			net.textContent = Math.max(0, value - computedFee).toFixed(2);
		}

		amount.addEventListener("input", update);
		update();
	}

	function initPeerCombobox() {
		document.querySelectorAll(".peer-combobox").forEach((box) => {
			const search = box.querySelector(".peer-search");
			const hidden = box.querySelector('input[name="to_membership_id"]');
			const list = box.querySelector(".peer-options");
			const options = Array.from(box.querySelectorAll(".peer-option"));
			const empty = document.createElement("div");
			let activeIndex = -1;

			if (!search || !hidden || !list) return;

			empty.className = "peer-empty";
			empty.textContent = "Однокурсник не найден";
			empty.hidden = true;
			list.append(empty);

			function visibleOptions() {
				return options.filter((option) => !option.hidden);
			}

			function setOpen(isOpen) {
				box.classList.toggle("is-open", isOpen);
				search.setAttribute("aria-expanded", String(isOpen));
			}

			function setActive(index) {
				visibleOptions().forEach((option) => option.classList.remove("is-active"));
				const visible = visibleOptions();
				activeIndex = Math.max(-1, Math.min(index, visible.length - 1));
				if (activeIndex >= 0) {
					visible[activeIndex].classList.add("is-active");
					visible[activeIndex].scrollIntoView({ block: "nearest" });
				}
			}

			function filterOptions() {
				const query = search.value.trim().toLowerCase();
				let found = 0;

				options.forEach((option) => {
					const haystack = `${option.textContent} ${option.dataset.search || ""}`.trim().toLowerCase();
					const matches = haystack.includes(query);
					option.hidden = !matches;
					if (matches) found += 1;
				});

				empty.hidden = found > 0;
				setActive(found ? 0 : -1);
			}

			function selectOption(option) {
				hidden.value = option.dataset.value || "";
				search.value = option.textContent.trim();
				search.setCustomValidity("");
				setOpen(false);
				setActive(-1);
			}

			search.addEventListener("focus", () => {
				filterOptions();
				setOpen(true);
			});

			search.addEventListener("input", () => {
				hidden.value = "";
				search.setCustomValidity("");
				filterOptions();
				setOpen(true);
			});

			search.addEventListener("keydown", (event) => {
				const visible = visibleOptions();

				if (event.key === "ArrowDown") {
					event.preventDefault();
					setOpen(true);
					setActive(activeIndex + 1 >= visible.length ? 0 : activeIndex + 1);
				}

				if (event.key === "ArrowUp") {
					event.preventDefault();
					setOpen(true);
					setActive(activeIndex <= 0 ? visible.length - 1 : activeIndex - 1);
				}

				if (event.key === "Enter" && box.classList.contains("is-open") && activeIndex >= 0) {
					event.preventDefault();
					selectOption(visible[activeIndex]);
				}

				if (event.key === "Escape") {
					setOpen(false);
				}
			});

			options.forEach((option) => {
				option.addEventListener("click", () => selectOption(option));
			});

			document.addEventListener("click", (event) => {
				if (!box.contains(event.target)) setOpen(false);
			});

			search.form?.addEventListener("submit", (event) => {
				if (!hidden.value) {
					search.setCustomValidity("Выберите однокурсника из списка");
					search.reportValidity();
					event.preventDefault();
				}
			});

			filterOptions();
		});
	}

	function initMenuState() {
		const tabs = Array.from(document.querySelectorAll("[data-tab]"));
		const panels = Array.from(document.querySelectorAll("[data-tab-panel]"));
		const app = document.querySelector(".student-app");
		if (!tabs.length || !panels.length) return;

		function selectTab(name) {
			tabs.forEach((tab) => {
				const isActive = tab.dataset.tab === name;
				tab.classList.toggle("is-active", isActive);
				tab.setAttribute("aria-selected", String(isActive));
			});
			panels.forEach((panel) => {
				const isActive = panel.dataset.tabPanel === name;
				panel.hidden = !isActive;
				panel.classList.toggle("is-active", isActive);
			});
			if (app) app.scrollTop = 0;
		}

		tabs.forEach((tab) => {
			tab.addEventListener("click", () => selectTab(tab.dataset.tab));
		});

		document.querySelectorAll("[data-return-home]").forEach((button) => {
			button.addEventListener("click", () => selectTab("home"));
		});

		selectTab("home");
	}

	function initHistoryBatches() {
		const rows = Array.from(document.querySelectorAll("[data-history-row]"));
		const button = document.querySelector("[data-load-history]");
		if (!button || !rows.length) return;

		function updateButton() {
			button.hidden = rows.every((row) => !row.hidden);
		}

		button.addEventListener("click", () => {
			rows.filter((row) => row.hidden).slice(0, 10).forEach((row) => {
				row.hidden = false;
			});
			updateButton();
		});

		updateButton();
	}

	function resultContainerFor(form) {
		const section = form.closest(".student-section");
		return section ? section.querySelector("[data-form-result]") : null;
	}

	function showResult(form, type, title, text) {
		const result = resultContainerFor(form);
		if (!result) return;
		form.hidden = true;
		result.hidden = false;
		result.classList.remove("success", "error");
		result.classList.add(type);
		result.querySelector("[data-result-title]").textContent = title;
		result.querySelector("[data-result-text]").textContent = text;
	}

	function initAsyncForms() {
		document.querySelectorAll(".async-member-form").forEach((form) => {
			form.addEventListener("submit", async (event) => {
				if (event.defaultPrevented) return;
				event.preventDefault();
				if (!form.reportValidity()) return;
				const message = form.dataset.confirmMessage || "Подтвердить действие?";
				if (!window.confirm(message)) return;

				const submitButton = form.querySelector('button[type="submit"]');
				if (submitButton) submitButton.disabled = true;

				try {
					const response = await window.fetch(form.action, {
						method: "POST",
						body: new URLSearchParams(new FormData(form)),
						headers: {
							"Content-Type": "application/x-www-form-urlencoded",
						},
					});

					if (response.ok || response.redirected) {
						if (form.classList.contains("reward-card")) {
							const button = form.querySelector(".reward-pay-button");
							if (button) {
								button.disabled = true;
								button.classList.add("paid");
								button.textContent = "Оплачено";
							}
						}
						showResult(form, "success", form.dataset.successMessage || "Готово", "Изменения сохранены. Вернитесь на главную, чтобы увидеть обновленный баланс.");
					} else {
						const errorText = await response.text();
						showResult(form, "error", "Не получилось", errorText || "Проверьте данные и попробуйте еще раз.");
						if (submitButton) submitButton.disabled = false;
					}
				} catch (error) {
					showResult(form, "error", "Ошибка сети", "Попробуйте повторить действие позже.");
					if (submitButton) submitButton.disabled = false;
				}
			});
		});
	}

	document.addEventListener("DOMContentLoaded", () => {
		initIcons();
		initCanvas();
		initTransferMath();
		initPeerCombobox();
		initMenuState();
		initHistoryBatches();
		initAsyncForms();
	});
})();
