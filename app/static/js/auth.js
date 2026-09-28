(function () {
	"use strict";

	const canvas = document.getElementById("auth-neural-canvas");
	const cursor = document.querySelector(".auth-cursor");
	const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

	if (canvas) {
		const ctx = canvas.getContext("2d");
		const target = { x: window.innerWidth / 2, y: window.innerHeight / 2 };
		let width = 0;
		let height = 0;
		let points = [];
		let frame = 0;

		function distance(a, b) {
			const dx = a.x - b.x;
			const dy = a.y - b.y;
			return dx * dx + dy * dy;
		}

		function buildPoints() {
			width = window.innerWidth;
			height = window.innerHeight;

			const ratio = Math.min(window.devicePixelRatio || 1, 2);
			canvas.width = Math.floor(width * ratio);
			canvas.height = Math.floor(height * ratio);
			canvas.style.width = `${width}px`;
			canvas.style.height = `${height}px`;
			ctx.setTransform(ratio, 0, 0, ratio, 0, 0);

			const stepX = Math.max(width / 18, 72);
			const stepY = Math.max(height / 14, 64);
			points = [];

			for (let x = 0; x <= width + stepX; x += stepX) {
				for (let y = 0; y <= height + stepY; y += stepY) {
					const originX = x + Math.random() * stepX - stepX / 2;
					const originY = y + Math.random() * stepY - stepY / 2;
					points.push({
						x: originX,
						y: originY,
						originX,
						originY,
						phase: Math.random() * Math.PI * 2,
						radius: 1.4 + Math.random() * 1.8,
						closest: [],
					});
				}
			}

			points.forEach((point) => {
				point.closest = points
					.filter((candidate) => candidate !== point)
					.sort((a, b) => distance(point, a) - distance(point, b))
					.slice(0, 5);
			});
		}

		function draw() {
			frame += 0.012;
			ctx.clearRect(0, 0, width, height);

			points.forEach((point) => {
				if (!reduceMotion) {
					point.x = point.originX + Math.sin(frame + point.phase) * 24;
					point.y = point.originY + Math.cos(frame * 0.9 + point.phase) * 24;
				}

				const dist = distance(point, target);
				let alpha = 0;
				let circleAlpha = 0;

				if (dist < 5200) {
					alpha = 0.34;
					circleAlpha = 0.78;
				} else if (dist < 22000) {
					alpha = 0.16;
					circleAlpha = 0.35;
				} else if (dist < 52000) {
					alpha = 0.055;
					circleAlpha = 0.16;
				}

				if (alpha) {
					point.closest.forEach((neighbor) => {
						ctx.beginPath();
						ctx.moveTo(point.x, point.y);
						ctx.lineTo(neighbor.x, neighbor.y);
						const redMix = Math.min(1, point.x / Math.max(width, 1));
						const r = Math.round(0 + 255 * redMix);
						const g = Math.round(200 - 200 * redMix);
						const b = Math.round(255 - 163 * redMix);
						ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${alpha})`;
						ctx.lineWidth = 1;
						ctx.stroke();
					});

					ctx.beginPath();
					ctx.arc(point.x, point.y, point.radius, 0, Math.PI * 2);
					ctx.fillStyle = `rgba(243, 251, 255, ${circleAlpha})`;
					ctx.fill();
				}
			});

			window.requestAnimationFrame(draw);
		}

		window.addEventListener("mousemove", (event) => {
			target.x = event.clientX;
			target.y = event.clientY;
		});

		window.addEventListener("touchmove", (event) => {
			const touch = event.touches[0];
			if (!touch) return;
			target.x = touch.clientX;
			target.y = touch.clientY;
		}, { passive: true });

		window.addEventListener("resize", buildPoints);

		buildPoints();
		draw();
	}

	if (cursor) {
		let cursorX = window.innerWidth / 2;
		let cursorY = window.innerHeight / 2;
		let nextX = cursorX;
		let nextY = cursorY;

		function moveCursor() {
			cursorX += (nextX - cursorX) * 0.22;
			cursorY += (nextY - cursorY) * 0.22;
			cursor.style.transform = `translate3d(${cursorX}px, ${cursorY}px, 0) translate3d(-50%, -50%, 0)`;
			window.requestAnimationFrame(moveCursor);
		}

		window.addEventListener("mousemove", (event) => {
			nextX = event.clientX;
			nextY = event.clientY;
			cursor.style.opacity = "1";
		});

		document.addEventListener("mouseenter", () => {
			cursor.style.opacity = "1";
		});

		document.addEventListener("mouseleave", () => {
			cursor.style.opacity = "0";
		});

		moveCursor();
	}

	document.querySelectorAll(".group-combobox").forEach((box) => {
		const search = box.querySelector(".group-search");
		const hidden = box.querySelector('input[name="group_id"]');
		const list = box.querySelector(".group-options");
		const options = Array.from(box.querySelectorAll(".group-option"));
		const empty = document.createElement("div");
		let activeIndex = -1;

		if (!search || !hidden || !list) return;

		empty.className = "group-empty";
		empty.textContent = "Группа не найдена";
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
				const matches = option.textContent.trim().toLowerCase().includes(query);
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
				search.setCustomValidity("Выберите группу из списка");
				search.reportValidity();
				event.preventDefault();
			}
		});

		filterOptions();
	});
})();
