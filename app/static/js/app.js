document.addEventListener("DOMContentLoaded", () => {
  if (window.lucide && typeof window.lucide.createIcons === "function") {
    window.lucide.createIcons({
      attrs: {
        "stroke-width": 2,
        "aria-hidden": "true",
      },
    });
  }

  const sidebar = document.querySelector("[data-sidebar]");
  const toggle = document.querySelector("[data-sidebar-toggle]");
  if (toggle && sidebar && !window.Alpine) {
    toggle.addEventListener("click", () => sidebar.classList.toggle("open"));
  }

  const confirmModal = document.querySelector("[data-confirm-modal]");
  const confirmTitle = confirmModal?.querySelector("[data-confirm-title]");
  const confirmMessage = confirmModal?.querySelector("[data-confirm-message]");
  const confirmAccept = confirmModal?.querySelector("[data-confirm-accept]");
  let pendingConfirmForm = null;

  function closeConfirmModal() {
    if (!confirmModal) return;
    confirmModal.hidden = true;
    pendingConfirmForm = null;
  }

  document.querySelectorAll("[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (form.dataset.confirmed === "true") {
        delete form.dataset.confirmed;
        return;
      }
      event.preventDefault();
      pendingConfirmForm = form;
      if (confirmTitle) confirmTitle.textContent = form.getAttribute("data-confirm-heading") || "Подтвердить действие?";
      if (confirmMessage) confirmMessage.textContent = form.getAttribute("data-confirm") || "Вы уверены?";
      if (confirmModal) {
        confirmModal.hidden = false;
        confirmAccept?.focus();
      }
    });
  });

  confirmModal?.querySelectorAll("[data-confirm-cancel]").forEach((button) => {
    button.addEventListener("click", closeConfirmModal);
  });

  confirmAccept?.addEventListener("click", () => {
    if (!pendingConfirmForm) return;
    pendingConfirmForm.dataset.confirmed = "true";
    pendingConfirmForm.requestSubmit();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && confirmModal && !confirmModal.hidden) closeConfirmModal();
  });

  function closeAdminModal(modal) {
    if (!modal) return;
    modal.hidden = true;
  }

  document.querySelectorAll("[data-admin-modal-open]").forEach((button) => {
    button.addEventListener("click", () => {
      const modal = document.getElementById(button.getAttribute("data-admin-modal-open"));
      if (!modal) return;
      modal.hidden = false;
      modal.querySelector("input, textarea, select, button")?.focus();
      window.lucide?.createIcons?.();
    });
  });

  document.querySelectorAll("[data-admin-modal-close]").forEach((button) => {
    button.addEventListener("click", () => closeAdminModal(button.closest("[data-admin-modal]")));
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    document.querySelectorAll("[data-admin-modal]:not([hidden])").forEach(closeAdminModal);
  });

  document.querySelectorAll(".alert").forEach((alert) => {
    window.setTimeout(() => {
      alert.style.opacity = "0";
      alert.style.transform = "translateY(-4px)";
    }, 5000);
  });

  document.querySelectorAll("[data-participant-search]").forEach((search) => {
    search.addEventListener("input", () => {
      const query = search.value.trim().toLowerCase();
      const panel = search.closest(".teacher-panel") || document;
      panel.querySelectorAll("[data-participant-row]").forEach((row) => {
        const match = row.textContent.toLowerCase().includes(query);
        row.style.display = match ? "" : "none";
      });
    });
  });

  function initAdminSelect(select) {
    if (select.dataset.enhancedSelect === "true") return;
    select.dataset.enhancedSelect = "true";
    select.classList.add("native-select");

    const wrapper = document.createElement("div");
    wrapper.className = "admin-combobox";

    const input = document.createElement("input");
    input.type = "text";
    input.className = "admin-combobox-input";
    input.autocomplete = "off";
    input.role = "combobox";
    input.setAttribute("aria-expanded", "false");
    input.placeholder = "Поиск";

    const list = document.createElement("div");
    list.className = "admin-combobox-options";
    list.role = "listbox";

    const empty = document.createElement("div");
    empty.className = "admin-combobox-empty";
    empty.textContent = "Ничего не найдено";
    empty.hidden = true;
    list.append(empty);

    select.parentNode.insertBefore(wrapper, select.nextSibling);
    wrapper.append(input, list);

    let activeIndex = -1;

    function options() {
      return Array.from(select.options);
    }

    function visibleButtons() {
      return Array.from(list.querySelectorAll(".admin-combobox-option")).filter((button) => !button.hidden);
    }

    function selectedText() {
      const selected = select.options[select.selectedIndex];
      return selected ? selected.textContent.trim() : "";
    }

    function setOpen(isOpen) {
      wrapper.classList.toggle("is-open", isOpen);
      input.setAttribute("aria-expanded", String(isOpen));
    }

    function setActive(index) {
      const visible = visibleButtons();
      visible.forEach((button) => button.classList.remove("is-active"));
      activeIndex = Math.max(-1, Math.min(index, visible.length - 1));
      if (activeIndex >= 0) {
        visible[activeIndex].classList.add("is-active");
        visible[activeIndex].scrollIntoView({ block: "nearest" });
      }
    }

    function selectValue(value) {
      select.value = value;
      input.value = selectedText();
      input.setCustomValidity("");
      select.dispatchEvent(new Event("change", { bubbles: true }));
      setOpen(false);
      setActive(-1);
    }

    function rebuild() {
      list.querySelectorAll(".admin-combobox-option").forEach((item) => item.remove());
      options().forEach((option) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "admin-combobox-option";
        button.role = "option";
        button.dataset.value = option.value;
        button.textContent = option.textContent.trim();
        button.disabled = option.disabled;
        const pickOption = (event) => {
          event.preventDefault();
          selectValue(option.value);
        };
        button.addEventListener("pointerdown", pickOption);
        button.addEventListener("mousedown", pickOption);
        button.addEventListener("click", () => selectValue(option.value));
        list.insertBefore(button, empty);
      });
      input.value = selectedText();
    }

    function syncSelectedText() {
      input.value = selectedText();
    }

    function filterOptions() {
      const query = input.value.trim().toLowerCase();
      let found = 0;
      list.querySelectorAll(".admin-combobox-option").forEach((button) => {
        const matches = button.textContent.trim().toLowerCase().includes(query);
        button.hidden = !matches;
        if (matches) found += 1;
      });
      empty.hidden = found > 0;
      setActive(found ? 0 : -1);
    }

    function openOptions() {
      input.value = "";
      filterOptions();
      setOpen(true);
    }

    input.addEventListener("focus", openOptions);
    input.addEventListener("click", openOptions);

    input.addEventListener("input", () => {
      filterOptions();
      setOpen(true);
    });

    input.addEventListener("keydown", (event) => {
      const visible = visibleButtons();
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
      if (event.key === "Enter" && wrapper.classList.contains("is-open") && activeIndex >= 0) {
        event.preventDefault();
        const button = visible[activeIndex];
        if (button) selectValue(button.dataset.value || "");
      }
      if (event.key === "Escape") {
        input.value = selectedText();
        setOpen(false);
      }
    });

    document.addEventListener("pointerdown", (event) => {
      if (wrapper.contains(event.target)) return;
      input.value = selectedText();
      setOpen(false);
    });

    select.addEventListener("change", syncSelectedText);

    rebuild();
  }

  document.querySelectorAll(".admin-body select").forEach(initAdminSelect);

  document.querySelectorAll("[data-expand-target]").forEach((button) => {
    button.addEventListener("click", () => {
      const target = document.getElementById(button.getAttribute("data-expand-target"));
      if (target) {
        target.classList.toggle("open");
        window.lucide?.createIcons?.();
      }
    });
  });

  const assessmentScope = document.querySelector("[data-assessment-scope]");
  if (assessmentScope) {
    const studentSelect = document.querySelector('select[name="student_membership_id"]');
    const studentLabel = document.querySelector("[data-assessment-student-field]") || studentSelect?.closest("label");

    function syncAssessmentFields() {
      const isStudent = assessmentScope.value === "student";
      if (studentLabel) studentLabel.hidden = !isStudent;
      if (studentSelect) {
        studentSelect.required = isStudent;
        if (!isStudent) {
          studentSelect.value = "";
          studentSelect.dispatchEvent(new Event("change", { bubbles: true }));
        }
      }
    }

    assessmentScope.addEventListener("change", syncAssessmentFields);
    syncAssessmentFields();
  }
});
