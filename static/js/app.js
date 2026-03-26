// Form submission handler
const form = document.getElementById("smartspend-form");
const submitButton = document.getElementById("submit-btn");
const questionInput = document.getElementById("id_question");

if (form && submitButton) {
    form.addEventListener("submit", () => {
        if (questionInput.value.trim()) {
            submitButton.disabled = true;
            submitButton.innerHTML = '<span class="btn-text">Analyzing<span class="dot-animation">.</span><span class="dot-animation">.</span><span class="dot-animation">.</span></span>';
        }
    });

    // Re-enable button if user starts typing again
    if (questionInput) {
        questionInput.addEventListener("input", () => {
            if (submitButton.disabled) {
                submitButton.disabled = false;
                submitButton.innerHTML = '<span class="btn-text">Analyze</span><span class="btn-icon">→</span>';
            }
        });
    }
}

// Query suggestion chips autofill the input with one click.
const suggestionChips = document.querySelectorAll(".suggestion-chip");
if (questionInput && suggestionChips.length > 0) {
    suggestionChips.forEach((chip) => {
        chip.addEventListener("click", () => {
            questionInput.value = chip.dataset.suggestion || "";
            questionInput.focus();
        });
    });
}

// Save query helper.
const saveQueryBtn = document.getElementById("save-query-btn");
const saveQueryTitle = document.getElementById("save-query-title");
const saveQueryForm = document.getElementById("save-query-form");
const saveQueryHiddenTitle = document.getElementById("save-query-hidden-title");
const saveQueryHiddenQuestion = document.getElementById("save-query-hidden-question");

if (saveQueryBtn && saveQueryTitle && saveQueryForm && questionInput) {
    saveQueryBtn.addEventListener("click", () => {
        const title = saveQueryTitle.value.trim();
        const question = questionInput.value.trim();
        if (!title || !question) {
            alert("Please enter both a query and a save title.");
            return;
        }
        saveQueryHiddenTitle.value = title;
        saveQueryHiddenQuestion.value = question;
        saveQueryForm.submit();
    });
}

// Scroll to results when they appear
document.addEventListener("DOMContentLoaded", () => {
    const resultsSection = document.querySelector(".results-section");
    if (resultsSection) {
        setTimeout(() => {
            resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
        }, 300);
    }

    // Click-to-view behavior for top dashboard cards.
    const statCards = Array.from(document.querySelectorAll(".stat-card[data-detail-target]"));
    const detailPanels = Array.from(document.querySelectorAll(".stat-detail-panel"));

    const showDetailPanel = (targetName) => {
        statCards.forEach((card) => {
            const isActive = card.dataset.detailTarget === targetName;
            card.classList.toggle("is-active", isActive);
            card.setAttribute("aria-pressed", String(isActive));
        });

        detailPanels.forEach((panel) => {
            const shouldShow = panel.id === `detail-${targetName}`;
            panel.classList.toggle("is-active", shouldShow);
            panel.hidden = !shouldShow;
        });
    };

    statCards.forEach((card) => {
        card.addEventListener("click", () => showDetailPanel(card.dataset.detailTarget));
        card.addEventListener("keydown", (evt) => {
            if (evt.key === "Enter" || evt.key === " ") {
                evt.preventDefault();
                showDetailPanel(card.dataset.detailTarget);
            }
        });
    });
});

// Copy to clipboard functionality
function copyToClipboard(event) {
    const code = document.querySelector("pre code");
    if (code) {
        const text = code.textContent;
        navigator.clipboard.writeText(text).then(() => {
            const btn = event.currentTarget;
            const originalText = btn.textContent;
            btn.textContent = "✓ Copied!";
            btn.style.background = "#10B981";
            btn.style.color = "white";
            
            setTimeout(() => {
                btn.textContent = originalText;
                btn.style.background = "";
                btn.style.color = "";
            }, 2000);
        }).catch(err => {
            console.error("Failed to copy:", err);
            alert("Failed to copy to clipboard");
        });
    }
}

// --- Dark mode toggle ---
(function() {
    const toggleBtn = document.getElementById('darkModeToggle');
    if (!toggleBtn) return;
    const root = document.body;
    // Check localStorage
    if (localStorage.getItem('theme') === 'dark') {
        root.classList.add('dark-mode');
    }
    toggleBtn.addEventListener('click', function() {
        root.classList.toggle('dark-mode');
        if (root.classList.contains('dark-mode')) {
            localStorage.setItem('theme', 'dark');
        } else {
            localStorage.setItem('theme', 'light');
        }
    });
})();
