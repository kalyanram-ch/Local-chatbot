const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const main = document.getElementById("messages");

const connectBtn = document.getElementById("connect-btn");
const disconnectBtn = document.getElementById("disconnect-btn");

const accountStatusText =
  document.getElementById("account-status-text");

const clearChatBtn =
  document.getElementById("clear-chat");

const suggestions =
  document.querySelectorAll(".suggestion");


// =====================================================
// HTML ESCAPE
// =====================================================

function escapeHtml(value) {

  const div = document.createElement("div");

  div.textContent = value ?? "";

  return div.innerHTML;
}


// =====================================================
// ADD USER MESSAGE
// =====================================================

function addUserMessage(text) {

  const row = document.createElement("div");

  row.className = "message-row user-row";

  row.innerHTML = `
    <div class="message user-message">
      <div class="message-text">
        ${escapeHtml(text)}
      </div>
    </div>
  `;

  main.appendChild(row);

  scrollToBottom();
}


// =====================================================
// ADD BOT MESSAGE
// =====================================================

function addBotMessage(text, results = []) {

  const row = document.createElement("div");

  row.className = "message-row bot-row";

  const avatar = document.createElement("div");

  avatar.className = "bot-avatar";

  avatar.innerHTML =
    `<i class="fa-solid fa-robot"></i>`;


  const message = document.createElement("div");

  message.className = "message bot-message";


  const textDiv = document.createElement("div");

  textDiv.className = "message-text";

  textDiv.textContent = text || "";


  message.appendChild(textDiv);


  if (results && results.length) {

    const resultsWrapper =
      createResults(results);

    message.appendChild(resultsWrapper);

  }


  row.appendChild(avatar);

  row.appendChild(message);

  main.appendChild(row);

  scrollToBottom();
}


// =====================================================
// RESULTS
// =====================================================

// Ordered list of known result sources: config drives both the section
// grouping below and the icon/label lookups in createResultSection /
// createResultCard, so adding a new source is a one-line change here.
const SOURCE_CONFIG = {
  gmail: { label: "Email Results", iconClass: "fa-regular fa-envelope", color: "#ea4335", colorClass: "source-gmail" },
  drive: { label: "Drive Results", iconClass: "fa-brands fa-google-drive", color: "#4285f4", colorClass: "source-drive" },
  calendar: { label: "Calendar Results", iconClass: "fa-regular fa-calendar", color: "#0f9d58", colorClass: "source-calendar" },
  sheets: { label: "Sheets Results", iconClass: "fa-solid fa-table-cells", color: "#0f9d58", colorClass: "source-sheets" },
  meet: { label: "Meet Results", iconClass: "fa-solid fa-video", color: "#00832d", colorClass: "source-meet" },
};


function createResults(results) {

  const wrapper =
    document.createElement("div");

  wrapper.className = "results-wrapper";


  Object.keys(SOURCE_CONFIG).forEach(source => {

    const sourceResults =
      results.filter(r => r.source === source);

    if (sourceResults.length) {

      wrapper.appendChild(
        createResultSection(
          source,
          SOURCE_CONFIG[source].label,
          sourceResults
        )
      );

    }

  });


  const security =
    document.createElement("div");

  security.className =
    "result-security";

  security.innerHTML = `
    <i class="fa-solid fa-shield-halved"></i>
    <span>
      Sensitive information has been automatically
      protected for your security.
    </span>
  `;

  wrapper.appendChild(security);


  return wrapper;
}


// =====================================================
// RESULT SECTION
// =====================================================

function createResultSection(
  source,
  title,
  results
) {

  const section =
    document.createElement("div");


  const titleRow =
    document.createElement("div");

  titleRow.className =
    "result-section-title";


  const config =
    SOURCE_CONFIG[source] || SOURCE_CONFIG.drive;

  const icon =
    `<i class="${config.iconClass}" style="color:${config.color}"></i>`;


  titleRow.innerHTML = `
    ${icon}
    <span>
      ${escapeHtml(title)}
      (${results.length})
    </span>

    <a href="#"
       class="view-all"
       onclick="return false;">
       View all →
    </a>
  `;


  section.appendChild(titleRow);


  const cards =
    document.createElement("div");


  results.forEach((result, index) => {

    cards.appendChild(
      createResultCard(
        result,
        index
      )
    );

  });


  section.appendChild(cards);

  return section;
}


// =====================================================
// RESULT CARD
// =====================================================

function createResultCard(result, index) {

  const card =
    document.createElement("div");

  card.className =
    "result-card";


  const config =
    SOURCE_CONFIG[result.source] || SOURCE_CONFIG.drive;

  const icon =
    document.createElement("div");

  icon.className =
    `source-icon ${config.colorClass}`;

  icon.innerHTML =
    `<i class="${config.iconClass}"></i>`;


  const info =
    document.createElement("div");

  info.className =
    "result-info";


  const title =
    document.createElement("div");

  title.className =
    "result-title";

  title.textContent =
    result.title || "(untitled)";


  const meta =
    document.createElement("div");

  meta.className =
    "result-meta";

  meta.textContent =
    `${result.meta || ""} · ${result.date || ""}`;


  info.appendChild(title);

  info.appendChild(meta);


  if (result.attachments &&
      result.attachments.length) {

    const attachmentList =
      document.createElement("div");

    attachmentList.className =
      "attachment-list";


    result.attachments.forEach(att => {

      const link =
        document.createElement("a");

      link.className =
        "attachment-link";

      link.href =
        att.download_url;

      link.innerHTML = `
        <i class="fa-solid fa-download"></i>
        ${escapeHtml(att.filename)}
      `;

      attachmentList.appendChild(link);

    });


    info.appendChild(attachmentList);

  }


  const relevance =
    document.createElement("div");

  relevance.className =
    `relevance ${
      index > 0 ? "normal" : ""
    }`;

  relevance.textContent =
    index === 0
      ? "Highly Relevant"
      : "Relevant";


  card.appendChild(icon);

  card.appendChild(info);

  card.appendChild(relevance);


  card.addEventListener(
    "click",
    event => {

      if (
        event.target.closest(
          ".attachment-link"
        )
      ) {
        return;
      }

      if (result.link) {
        window.open(
          result.link,
          "_blank",
          "noopener,noreferrer"
        );
      }

    }
  );


  return card;
}


// =====================================================
// TYPING INDICATOR
// =====================================================

function showTyping() {

  const row =
    document.createElement("div");

  row.id =
    "typing-indicator";

  row.className =
    "message-row bot-row";


  row.innerHTML = `
    <div class="bot-avatar">
      <i class="fa-solid fa-robot"></i>
    </div>

    <div class="message bot-message">

      <div class="typing">

        <span></span>
        <span></span>
        <span></span>

      </div>

    </div>
  `;


  main.appendChild(row);

  scrollToBottom();
}


// =====================================================
// REMOVE TYPING
// =====================================================

function hideTyping() {

  const typing =
    document.getElementById(
      "typing-indicator"
    );

  if (typing) {
    typing.remove();
  }
}


// =====================================================
// SCROLL
// =====================================================

function scrollToBottom() {

  requestAnimationFrame(() => {

    main.scrollTo({
      top: main.scrollHeight,
      behavior: "smooth"
    });

  });

}


// =====================================================
// GOOGLE STATUS
// =====================================================

async function refreshStatus() {

  try {

    const response =
      await fetch("/api/status");

    const data =
      await response.json();


    const connected =
      Boolean(data.authenticated);


    connectBtn.dataset.connected =
      connected;


    if (connected) {

      connectBtn.innerHTML = `
        <i class="fa-solid fa-circle-check"></i>
        <span>Google Connected</span>
      `;

      accountStatusText.textContent =
        "Google Connected";

      disconnectBtn.disabled =
        false;

    } else {

      connectBtn.innerHTML = `
        <i class="fa-brands fa-google"></i>
        <span>Connect Google</span>
      `;

      accountStatusText.textContent =
        "Not connected";

      disconnectBtn.disabled =
        true;

    }

  } catch (error) {

    console.error(
      "Status error:",
      error
    );

  }

}


// =====================================================
// GOOGLE CONNECT
// =====================================================

connectBtn.addEventListener(
  "click",
  async () => {

    if (
      connectBtn.dataset.connected ===
      "true"
    ) {
      return;
    }


    connectBtn.disabled =
      true;

    connectBtn.innerHTML = `
      <i class="fa-solid fa-spinner fa-spin"></i>
      <span>Connecting...</span>
    `;


    try {

      const response =
        await fetch("/api/authorize");

      const data =
        await response.json();


      if (!data.ok) {

        addBotMessage(
          `Couldn't connect to Google: ${data.error}`
        );

        return;
      }


      const popup =
        window.open(
          data.authUrl,
          "_blank",
          "noopener,noreferrer"
        );


      if (!popup) {

        addBotMessage(
          "Your browser blocked the Google sign-in popup. Please allow popups and try again."
        );

      } else {

        addBotMessage(
          "Google sign-in opened in a new tab. Approve the read-only Gmail and Drive permissions, then return here."
        );

      }


      pollForConnection();

    } catch (error) {

      addBotMessage(
        `Connection failed: ${error.message}`
      );

    } finally {

      connectBtn.disabled =
        false;

    }

  }
);


// =====================================================
// POLL GOOGLE CONNECTION
// =====================================================

async function pollForConnection(
  attemptsLeft = 60
) {

  if (attemptsLeft <= 0) {

    refreshStatus();

    return;
  }


  await new Promise(
    resolve =>
      setTimeout(resolve, 2000)
  );


  try {

    const response =
      await fetch("/api/status");

    const data =
      await response.json();


    if (data.authenticated) {

      connectBtn.dataset.connected =
        "true";

      connectBtn.innerHTML = `
        <i class="fa-solid fa-circle-check"></i>
        <span>Google Connected</span>
      `;

      accountStatusText.textContent =
        "Google Connected";

      disconnectBtn.disabled =
        false;


      addBotMessage(
        "Google account connected successfully! You can now search your Gmail and Google Drive."
      );


      return;
    }

  } catch (error) {

    console.error(error);

  }


  pollForConnection(
    attemptsLeft - 1
  );
}


// =====================================================
// DISCONNECT
// =====================================================

disconnectBtn.addEventListener(
  "click",
  async () => {

    if (disconnectBtn.disabled) {
      return;
    }


    disconnectBtn.disabled =
      true;


    disconnectBtn.innerHTML = `
      <i class="fa-solid fa-spinner fa-spin"></i>
      Disconnecting...
    `;


    try {

      await fetch(
        "/api/disconnect",
        {
          method: "POST"
        }
      );


      addBotMessage(
        "Your Google account has been disconnected and the local authorization session was cleared."
      );


      await refreshStatus();

    } catch (error) {

      addBotMessage(
        `Disconnect failed: ${error.message}`
      );

    }

  }
);


// =====================================================
// CHAT
// =====================================================

chatForm.addEventListener(
  "submit",
  async event => {

    event.preventDefault();


    const text =
      chatInput.value.trim();


    if (!text) {
      return;
    }


    addUserMessage(text);


    chatInput.value = "";

    chatInput.focus();


    const sendButton =
      document.getElementById(
        "send-btn"
      );

    sendButton.disabled =
      true;


    showTyping();


    try {

      const response =
        await fetch(
          "/api/chat",
          {
            method: "POST",

            headers: {
              "Content-Type":
                "application/json"
            },

            body: JSON.stringify({
              message: text
            })
          }
        );


      const data =
        await response.json();


      hideTyping();


      addBotMessage(
        data.reply ||
        "I couldn't generate a response.",
        data.results || []
      );


    } catch (error) {

      hideTyping();


      addBotMessage(
        "Sorry, something went wrong while processing your request. Please try again."
      );


      console.error(
        "Chat error:",
        error
      );

    } finally {

      sendButton.disabled =
        false;

      chatInput.focus();

    }

  }
);


// =====================================================
// SUGGESTIONS
// =====================================================

suggestions.forEach(
  button => {

    button.addEventListener(
      "click",
      () => {

        chatInput.value =
          button.textContent.trim();

        chatInput.focus();

      }
    );

  }
);


// =====================================================
// CLEAR CHAT
// =====================================================

clearChatBtn.addEventListener(
  "click",
  () => {

    main.innerHTML = `
      <div class="welcome-card">

        <div class="welcome-icon">
          <i class="fa-solid fa-wand-magic-sparkles"></i>
        </div>

        <div>

          <div class="welcome-title">
            EIDIKO AI Assistant
          </div>

          <div class="welcome-description">
            Search Gmail, Drive & get intelligent answers
          </div>

        </div>

        <button
          id="clear-chat"
          class="clear-btn">

          <i class="fa-regular fa-trash-can"></i>
          Clear Chat

        </button>

      </div>
    `;


    // Re-bind clear button
    document
      .getElementById("clear-chat")
      .addEventListener(
        "click",
        () => location.reload()
      );


    addBotMessage(
      "Chat cleared. What would you like me to find?"
    );

  }
);


// =====================================================
// SIDEBAR MENU
// =====================================================

document
  .querySelectorAll(".menu-item")
  .forEach(item => {

    item.addEventListener(
      "click",
      () => {

        document
          .querySelectorAll(".menu-item")
          .forEach(
            el =>
              el.classList.remove(
                "active"
              )
          );


        item.classList.add(
          "active"
        );


        const section =
          item.dataset.section;


        if (section !== "chat") {

          addBotMessage(
            `${item.textContent.trim()} is available from the navigation. Your current EIDIKO search workflow remains active.`
          );

        }

      }
    );

  });


// =====================================================
// START
// =====================================================

refreshStatus();

chatInput.focus();