let activeFilter = 'all';
let latestHealth = null;
let latestTranscriptData = null;

function escapeHtml(s) {
  return String(s ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}

function setLog(id, msg) {
  const el = document.getElementById(id);
  if (el) el.textContent = msg;
}

function isLiveRow(row) {
  const lane = String(row.lane || '').toLowerCase();
  const source = String(row.source || '').toLowerCase();
  return (
    lane.includes('live') ||
    source.includes('live') ||
    row.live === true ||
    row.live_reactive === true
  );
}

function formatMessageContent(raw) {
  const text = String(raw || '');
  const fenceIdx = text.indexOf('```json');
  if (fenceIdx === -1) {
    return `<div class="msg-body">${escapeHtml(text)}</div>`;
  }
  const head = text.slice(0, fenceIdx).trim();
  const rest = text.slice(fenceIdx + 7);
  const endIdx = rest.indexOf('```');
  const jsonPart = (endIdx !== -1 ? rest.slice(0, endIdx) : rest).trim();
  return (
    `<div class="msg-body">${escapeHtml(head)}</div>` +
    `<pre class="msg-json">${escapeHtml(jsonPart)}</pre>`
  );
}

function renderMetaChips() {
  const meta = document.getElementById('meta');
  if (!meta) return;
  const rows = latestTranscriptData?.rows || [];
  const counts = latestTranscriptData?.counts || {
    total: rows.length,
    live: rows.filter(isLiveRow).length,
    sandbox: rows.filter((r) => !isLiveRow(r)).length,
  };
  const lb = latestHealth?.live_bridge || {};
  const lbOk = Boolean(lb.reachable && lb.status?.ok);
  const wsMap = lb.status?.ws_connected || {};
  const wsUpCount = Object.values(wsMap).filter(Boolean).length;
  const wsTotal = Object.keys(wsMap).length || 3;

  meta.innerHTML = `
    <span class="pill ok">PREVIEW :18765 (127.0.0.1 + ::1)</span>
    <span class="pill ${lbOk ? 'ok' : 'danger'}">
      ${lbOk ? `LIVE BRIDGE :18766 · WS ${wsUpCount}/${wsTotal}` : 'LIVE BRIDGE DOWN'}
    </span>
    <span class="pill">ROWS: ${counts.total} (${counts.live} LIVE / ${counts.sandbox} SANDBOX)</span>
    <span class="pill purple">DETERMINISTIC · NO LLM</span>
    <span class="pill warn">REVIEW: PENDING</span>
  `;
}

function renderTranscript() {
  const el = document.getElementById('transcript');
  if (!el || !latestTranscriptData) return;
  const rows = latestTranscriptData.rows || [];
  const liveRows = rows.filter(isLiveRow);
  const sandboxRows = rows.filter((r) => !isLiveRow(r));

  const cntAll = document.getElementById('cntAll');
  const cntLive = document.getElementById('cntLive');
  const cntSandbox = document.getElementById('cntSandbox');
  if (cntAll) cntAll.textContent = String(rows.length);
  if (cntLive) cntLive.textContent = String(liveRows.length);
  if (cntSandbox) cntSandbox.textContent = String(sandboxRows.length);

  let filtered = rows;
  if (activeFilter === 'live') filtered = liveRows;
  if (activeFilter === 'sandbox') filtered = sandboxRows;

  el.innerHTML = '';
  for (const row of filtered.slice(-100)) {
    const div = document.createElement('div');
    const role = row.role || 'unknown';
    const live = isLiveRow(row);
    const laneLabel = live ? 'LIVE · SWITCH ROOM' : 'SANDBOX · DRY-RUN';
    const badgeClass = live ? 'live' : 'sandbox';
    const actionChip = row.action ? ` · <code>${escapeHtml(row.action)}</code>` : '';
    const intentChip = row.intent ? ` · <code>${escapeHtml(row.intent)}</code>` : '';
    const tsShort = String(row.ts || '').replace('T', ' ').slice(0, 19);

    div.className = `msg ${role}` + (live ? ' live' : '');
    div.innerHTML = `
      <div class="msg-head">
        <div class="role">
          <span class="badge-inline ${badgeClass}">${laneLabel}</span>
          <span class="role-name">${escapeHtml(role)}</span>
          ${intentChip}${actionChip}
        </div>
        <span class="role">${escapeHtml(tsShort)}</span>
      </div>
      ${formatMessageContent(row.content || '')}
    `;
    el.appendChild(div);
  }
  if (!filtered.length) {
    el.innerHTML = '<div class="msg">No matching transcript rows yet. Dispatch a LIVE task above.</div>';
  }
  el.scrollTop = el.scrollHeight;

  const briefEl = document.getElementById('lastBrief');
  if (briefEl && latestTranscriptData.last_brief) {
    briefEl.textContent = latestTranscriptData.last_brief;
  } else if (briefEl) {
    briefEl.textContent = 'No brief recorded yet. Send a LIVE task to trigger gw-scribe.';
  }
}

async function loadHealthAndTranscript() {
  try {
    const [hRes, tRes] = await Promise.all([
      fetch('/api/health'),
      fetch('/api/transcript'),
    ]);
    latestHealth = await hRes.json();
    latestTranscriptData = await tRes.json();
    renderMetaChips();
    renderTranscript();
  } catch (e) {
    const el = document.getElementById('transcript');
    if (el) el.innerHTML = `<div class="msg">Transcript fetch error: ${escapeHtml(String(e))}</div>`;
  }
}

async function loadSandboxApprovals() {
  const el = document.getElementById('approvals');
  if (!el) return;
  try {
    const res = await fetch('/api/approvals');
    const data = await res.json();
    el.innerHTML = '';
    if (!data.pending || !data.pending.length) {
      el.innerHTML = '<p class="muted">No pending sandbox approvals.</p>';
      return;
    }
    for (const a of data.pending) {
      const card = document.createElement('div');
      card.className = 'approval';
      card.innerHTML = `
        <div class="role">
          <span class="badge-inline sandbox">SANDBOX</span>
          <span class="role-name">${escapeHtml(a.approval_id)}</span>
          · <code>${escapeHtml(a.intent)}</code>
          · risk: ${escapeHtml(a.risk || 'low')}
        </div>
        <div style="margin-top:4px">${escapeHtml(a.summary)}</div>
        <div class="row" style="margin-top:8px">
          <button type="button" class="okbtn" data-id="${escapeHtml(a.approval_id)}" data-dec="approve">Approve Sandbox (Dry-Run)</button>
          <button type="button" class="denybtn" data-id="${escapeHtml(a.approval_id)}" data-dec="reject">Reject Sandbox</button>
        </div>
      `;
      el.appendChild(card);
    }
    el.querySelectorAll('button[data-dec]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const r = await fetch('/api/decide', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ approval_id: btn.dataset.id, decision: btn.dataset.dec }),
        });
        const j = await r.json();
        setLog('actionLog', (j.receipt || j.message || '') + (j.idempotent ? ' [idempotent]' : ''));
        await refresh();
      });
    });
  } catch (e) {
    el.innerHTML = `<p class="muted">Sandbox approvals error: ${escapeHtml(String(e))}</p>`;
  }
}

async function loadLive() {
  const st = document.getElementById('liveStatus');
  const ap = document.getElementById('liveApprovals');
  if (!st || !ap) return;
  try {
    const r = await fetch('/api/live/status');
    const j = await r.json();
    if (!j.ok) {
      st.innerHTML = `<span class="pill danger">LIVE bridge down</span> <span>${escapeHtml(j.error || JSON.stringify(j))}</span>`;
      ap.innerHTML = '';
      return;
    }
    const sessions = j.sessions || {};
    const sessBadges = Object.entries(sessions)
      .map(([name, info]) => `<span class="pill ${info.connected ? 'ok' : 'warn'}">${escapeHtml(name)}: ${info.connected ? 'WS connected' : 'reconnecting'}</span>`)
      .join(' ');
    const roomShort = String(j.room_id || '').slice(0, 8);
    st.innerHTML = `
      <span class="pill ok">LIVE ROOM READY</span>
      <span class="pill">room <code>${escapeHtml(roomShort)}…</code></span>
      <span class="pill">audit turns: ${escapeHtml(String((j.recent || []).length))}</span>
      ${sessBadges}
    `;
    if (j.last_brief) {
      const briefEl = document.getElementById('lastBrief');
      if (briefEl) briefEl.textContent = j.last_brief;
    }
    ap.innerHTML = '';
    const pending = j.pending_approvals || [];
    if (!pending.length) {
      ap.innerHTML = '<p class="muted">No LIVE pending approvals in Switch room.</p>';
    }
    for (const a of pending) {
      const card = document.createElement('div');
      card.className = 'approval live';
      card.innerHTML = `
        <div class="role">
          <span class="badge-inline live">LIVE SWITCH</span>
          <span class="role-name">${escapeHtml(a.approval_id)}</span>
          · <code>${escapeHtml(a.intent)}</code>
        </div>
        <div style="margin-top:4px">${escapeHtml(a.summary || '')}</div>
        <div class="row" style="margin-top:8px">
          <button type="button" class="okbtn" data-lid="${escapeHtml(a.approval_id)}" data-ldec="approve">Approve LIVE (Dry-Run Receipt)</button>
          <button type="button" class="denybtn" data-lid="${escapeHtml(a.approval_id)}" data-ldec="reject">Reject LIVE</button>
        </div>
      `;
      ap.appendChild(card);
    }
    ap.querySelectorAll('button[data-lid]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        setLog('liveLog', `Sending LIVE ${btn.dataset.ldec} ${btn.dataset.lid} to Switch room…`);
        const r2 = await fetch('/api/live/decide', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ approval_id: btn.dataset.lid, decision: btn.dataset.ldec }),
        });
        const j2 = await r2.json();
        setLog('liveLog', j2.message || j2.receipt || JSON.stringify(j2));
        setTimeout(refresh, 1500);
      });
    });
  } catch (e) {
    st.innerHTML = `<span class="pill danger">LIVE unreachable</span> ${escapeHtml(String(e))}`;
  }
}

async function liveSend(text) {
  setLog('liveLog', `Dispatching [human] "${text}" into Switch room via send_targeted_message…`);
  const r = await fetch('/api/live/send', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
  const j = await r.json();
  setLog(
    'liveLog',
    j.ok
      ? `LIVE room accepted: "${text}" · external_side_effect=${j.executed_external_side_effect}`
      : `LIVE error: ${j.error || JSON.stringify(j)}`
  );
  await refresh();
  setTimeout(refresh, 2000);
}

async function sandboxSim(text) {
  const r = await fetch('/api/simulate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
  const j = await r.json();
  setLog(
    'actionLog',
    `[SANDBOX ${j.decision}] intent=${j.intent || 'unknown'} · side_effect=${j.executed_side_effect}`
  );
  await refresh();
}

async function refresh() {
  await Promise.all([loadHealthAndTranscript(), loadSandboxApprovals(), loadLive()]);
}

document.getElementById('liveSend').addEventListener('click', () => {
  const t = document.getElementById('liveText').value.trim();
  if (t) liveSend(t);
});

document.getElementById('liveText').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    const t = e.target.value.trim();
    if (t) liveSend(t);
  }
});

document.querySelectorAll('[data-live]').forEach((b) =>
  b.addEventListener('click', () => {
    document.getElementById('liveText').value = b.dataset.live;
    liveSend(b.dataset.live);
  })
);

document.getElementById('simBtn').addEventListener('click', () => {
  const t = document.getElementById('simText').value.trim();
  if (t) sandboxSim(t);
});

document.getElementById('simText').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    const t = e.target.value.trim();
    if (t) sandboxSim(t);
  }
});

document.querySelectorAll('[data-sim]').forEach((b) =>
  b.addEventListener('click', () => {
    document.getElementById('simText').value = b.dataset.sim;
    sandboxSim(b.dataset.sim);
  })
);

document.querySelectorAll('.filter-btn').forEach((btn) =>
  btn.addEventListener('click', () => {
    document.querySelectorAll('.filter-btn').forEach((b) => b.classList.remove('active'));
    btn.classList.add('active');
    activeFilter = btn.dataset.filter || 'all';
    renderTranscript();
  })
);

refresh();
setInterval(refresh, 4000);
