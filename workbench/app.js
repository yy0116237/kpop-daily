/* ============ KPOP DAILY 2.0 工作台 · 前端逻辑 ============ */
'use strict';

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];

const state = { data: null, daily: null, dailyDate: null, prefill: null, itemFilter: { status: 'all', kind: 'all' }, conFilter: { group: 'all' } };

/* ---------- 工具 ---------- */
async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...opts });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || ('HTTP ' + r.status));
  return j;
}
function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function toast(msg) {
  const t = $('#toast'); t.textContent = msg; t.hidden = false;
  clearTimeout(t._tm); t._tm = setTimeout(() => (t.hidden = true), 2200);
}
function todayStr() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
const TYPE_LABEL = { comeback: '回归期', 'pre-release': '先行曲', album: '专辑', showcase: 'Showcase', tour: '巡演', birthday: '生日', anniversary: '周年', ticketing: '抢票日', other: '日程' };
const TICKET_LABEL = { not_open: '未开票', upcoming: '待抢', won: '已抢到', lost: '未抢到', attended: '已入场' };
function inferType(cat, title) {
  if (cat === 'comeback') return 'comeback';
  const t = title || '';
  if (/tour|巡演|콘서트/i.test(t)) return 'tour';
  if (/pre-?release|先行|선공개/i.test(t)) return 'pre-release';
  if (/album|专辑|미니/i.test(t)) return 'album';
  if (/showcase/i.test(t)) return 'showcase';
  return 'other';
}

/* ---------- 收藏区（M3）标签映射 ---------- */
const KIND_LABEL = { album: '专辑', photocard: '小卡', merch: '周边', other: '其他' };
const KIND_ICON = { album: '辑', photocard: '卡', merch: '物', other: '★' };
const STATUS_LABEL = { wishlist: '种草', ordered: '在途', owned: '已到手', sold: '已出物' };
const STATUS_CLASS = { wishlist: 'st-wish', ordered: 'st-order', owned: 'st-owned', sold: 'st-sold' };
const PLATFORM_LABEL = { k4: 'k4', amazon_jp: '日亚', xianyu: '闲鱼', offline: '线下', other: '其他' };

/* ---------- Con 记忆区（M4）标签映射 ---------- */
const EXP_LABEL = { ticket: '票', transport: '交通', hotel: '住宿', food: '餐饮', merch: '周边', other: '其他' };
const MOOD_STAR = { 5: '★★★★★', 4: '★★★★', 3: '★★★', 2: '★★', 1: '★' };

/* ---------- 初始化 ---------- */
async function init() {
  try {
    const [data, d] = await Promise.all([api('/api/data'), api('/api/daily')]);
    state.data = data; state.daily = d.daily; state.dailyDate = d.date;
    renderDaily(); renderEvents(); renderItems(); renderCons(); fillGroupList(); bindStatic(); renderLedger();
    $('#status').textContent = d.date ? `日报 ${d.date}` : '本地数据';
  } catch (e) {
    $('#status').classList.add('off');
    $('#hero-lead').textContent = '连接本地服务失败：' + e.message;
  }
}

/* ---------- 日报渲染（左列 + 底部榜单） ---------- */
function isChartSec(label) { return /榜单|chart/i.test(label || ''); }

function renderDaily() {
  if (!state.daily) return;
  const d = state.daily;
  $('#hero-date').textContent = 'DAILY BRIEFING · ' + d.date + ' · KST';
  $('#hero-lead').textContent = (d.lead || '今日暂无头条').slice(0, 130);

  const fl = $('#flashes'); fl.innerHTML = '';
  (d.flashes || []).slice(0, 5).forEach(f => {
    const a = document.createElement('a');
    a.className = 'flash'; a.textContent = f.text;
    a.href = f.link || '#'; a.target = '_blank'; a.rel = 'noopener';
    fl.appendChild(a);
  });

  const secBox = $('#news-sections'); secBox.innerHTML = '';
  const chartBox = $('#chart-list'); chartBox.innerHTML = '';
  let chartSeen = false;

  (d.sections || []).forEach(s => {
    const items = s.items || [];
    if (isChartSec(s.label)) {
      if (!chartSeen) {
        chartSeen = true;
        const it0 = items[0] || {};
        const srcKeys = Object.keys(it0.perSourceRank || {}).map(k => k.charAt(0).toUpperCase() + k.slice(1));
        const srcName = srcKeys.length ? srcKeys.join(' + ') : ((it0.source && it0.source.name) || '音源榜');
        const idm = String(it0.id || '').match(/(\d{4}-\d{2}-\d{2})/);
        const chartDate = idm ? idm[1] : (state.dailyDate || '');
        let hhmm = '';
        const pT = it0.publishedAt || '';
        if (pT.includes('T')) {
          const t = pT.split('T')[1].slice(0, 5);
          if (t && t !== '00:00') hhmm = t;
        }
        if (!hhmm && it0.discoveredAt && it0.discoveredAt.includes('T')) {
          const t = it0.discoveredAt.split('T')[1].slice(0, 5);
          if (t) hhmm = t;
        }
        $('#chart-title').textContent = `数据 · 榜单（${srcName}）`;
        $('#chart-meta').textContent = hhmm
          ? `榜单截至 ${chartDate} ${hhmm}（KST）`
          : `榜单日期 ${chartDate} · 实时排名`;
      }
      items.forEach(it => {
        const rank = (it.perSourceRank && (it.perSourceRank.melon ?? it.perSourceRank.circle)) || it.rank || '';
        const artist = it.artist || it.album || '';
        const el = document.createElement('div'); el.className = 'crow';
        el.innerHTML = `<span class="rank">${esc(rank ? '#' + rank : '·')}</span>` +
          `<span class="t">${esc(it.title)}</span>` +
          (artist ? `<span class="a">${esc(artist)}</span>` : '');
        chartBox.appendChild(el);
      });
      return;
    }
    const secEl = document.createElement('div'); secEl.className = 'news-sec';
    secEl.innerHTML = `<div class="sec-head"><h3>${esc(s.label)}</h3><span class="cnt">${items.length} 条</span></div><div class="news-grid"></div>`;
    const grid = $('.news-grid', secEl);
    items.forEach(it => {
      const canLink = ['comeback', 'stage', 'event'].includes(it.category) && (it.groups || []).length;
      const src = (it.source && it.source.name) || '';
      const groups = (it.groups || []).slice(0, 4);
      const card = document.createElement('div'); card.className = 'item-card';
      card.innerHTML = `
        <div class="item-top">${src ? `<span class="src">${esc(src)}</span>` : ''}${it.category ? `<span class="src">${esc(it.category)}</span>` : ''}</div>
        <div class="item-title">${esc(it.title)}</div>
        ${it.summary ? `<div class="item-sum">${esc(it.summary)}</div>` : ''}
        <div class="item-foot">
          <div class="groups">${groups.map(g => `<span class="grp">${esc(g)}</span>`).join('')}</div>
          ${canLink ? `<button class="btn-add-ev" data-group="${esc(groups[0])}" data-title="${esc(it.title)}" data-cat="${esc(it.category)}" data-id="${esc(it.id)}" data-url="${esc((it.links && it.links.original) || '')}">＋ 加入日程</button>` : ''}
        </div>`;
      grid.appendChild(card);
    });
    secBox.appendChild(secEl);
  });
}

/* ---------- 日程区（右上角，M1） ---------- */
function nextDate(ev) {
  const base = ev.startDate || '';
  if (!base || !/^\d{4}-\d{2}-\d{2}/.test(base)) return null;
  if (ev.repeat === 'yearly') {
    const now = new Date();
    const y = now.getFullYear();
    const d = new Date(y, +base.slice(5, 7) - 1, +base.slice(8, 10));
    const today = new Date(y, now.getMonth(), now.getDate());
    if (d < today) d.setFullYear(y + 1);
    return d;
  }
  return new Date(base.slice(0, 10) + 'T00:00:00');
}
function fmtMMDD(dt) {
  return `${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}`;
}

function renderEvents() {
  const list = $('#event-list'); list.innerHTML = '';
  const evs = (state.data.events || [])
    .map(ev => ({ ev, nd: nextDate(ev) }))
    .filter(x => x.nd)
    .sort((a, b) => a.nd - b.nd);
  $('#event-hint').style.display = evs.length ? 'none' : 'block';

  const today = new Date(); today.setHours(0, 0, 0, 0);
  evs.slice(0, 14).forEach(({ ev, nd }) => {
    const diff = Math.round((nd - today) / 86400000);
    const due = diff >= 0 && diff <= 7;
    const sub = [];
    if (ev.type) sub.push(TYPE_LABEL[ev.type] || ev.type);
    if (ev.location) sub.push(ev.location);
    if (ev.ticketStatus) sub.push(TICKET_LABEL[ev.ticketStatus] || ev.ticketStatus);
    const badge = due ? '7天内' : fmtMMDD(nd) + (ev.repeat === 'yearly' ? '·年' : diff < 0 ? '·已过' : '');
    const el = document.createElement('div'); el.className = 'evt' + (due ? ' due' : '');
    el.innerHTML = `
      <span class="evt-date">${esc(badge)}</span>
      <div class="evt-body">
        <div class="evt-title">${esc(ev.title)}</div>
        <div class="evt-sub">${esc(sub.join(' · '))}</div>
      </div>
      <button class="evt-del" data-id="${esc(ev.id)}" title="删除">✕</button>`;
    list.appendChild(el);
  });
}

/* ---------- 收藏区（M3） ---------- */
function renderItems() {
  const f = state.itemFilter || { status: 'all', kind: 'all' };
  const list = $('#item-list'); list.innerHTML = '';
  const all = state.data.items || [];
  const items = all.filter(it => {
    if (f.status !== 'all' && (it.status || 'owned') !== f.status) return false;
    if (f.kind !== 'all' && it.kind !== f.kind) return false;
    return true;
  });
  $('#item-hint').style.display = all.length ? 'none' : 'block';

  items.forEach(it => {
    const st = it.status || 'owned';
    const thumb = it.image
      ? `<div class="ithumb"><span class="ph">${esc(KIND_ICON[it.kind] || '★')}</span><img src="/file/${encodeURIComponent(it.image)}" alt="" onerror="this.remove()"></div>`
      : `<div class="ithumb"><span class="ph">${esc(KIND_ICON[it.kind] || '★')}</span></div>`;
    const amt = it.amount != null ? `<span class="iamt">¥${Number(it.amount).toLocaleString()}</span>` : '';
    const orig = (it.originalAmount != null && it.originalCurrency)
      ? `<span class="iorig">原 ${esc(it.originalCurrency)} ${esc(it.originalAmount)}</span>` : '';
    const meta = [PLATFORM_LABEL[it.platform] || '', it.purchasedDate || ''].filter(Boolean).join(' · ');
    const card = document.createElement('div'); card.className = 'item-card2';
    card.innerHTML = `
      ${thumb}
      <div class="icard-body">
        <div class="icard-top">
          <span class="badge ${STATUS_CLASS[st]}">${STATUS_LABEL[st]}</span>
          <span class="ikind">${KIND_LABEL[it.kind] || '其他'}</span>
        </div>
        <div class="iname"><b>${esc(it.group || '未填团体')}</b> <span class="sep">·</span> ${esc(it.name || '未命名')}</div>
        ${it.version ? `<div class="iver">${esc(it.version)}</div>` : ''}
        ${meta ? `<div class="imeta">${esc(meta)}</div>` : ''}
        <div class="iprice">${amt}${orig ? ' ' + orig : ''}</div>
        ${it.note ? `<div class="inote">${esc(it.note)}</div>` : ''}
      </div>
      <div class="icard-actions">
        <button class="mini edit" data-id="${esc(it.id)}">编辑</button>
        <button class="mini del" data-id="${esc(it.id)}">删除</button>
      </div>`;
    list.appendChild(card);
  });
}

function openItemModal(it) {
  $('#item-modal-title').textContent = it ? '编辑收藏' : '新增收藏';
  $('#i-id').value = it ? it.id : '';
  $('#i-kind').value = (it && it.kind) || 'album';
  $('#i-status').value = (it && it.status) || 'owned';
  $('#i-group').value = (it && it.group) || '';
  $('#i-name').value = (it && it.name) || '';
  $('#i-version').value = (it && it.version) || '';
  $('#i-platform').value = (it && it.platform) || '';
  $('#i-date').value = (it && it.purchasedDate) || '';
  $('#i-amount').value = (it && it.amount != null) ? it.amount : '';
  $('#i-orig').value = (it && it.originalAmount != null) ? it.originalAmount : '';
  $('#i-origc').value = (it && it.originalCurrency) || '';
  $('#i-image').value = (it && it.image) || '';
  $('#i-note').value = (it && it.note) || '';
  $('#item-mask').hidden = false;
  $('#i-name').focus();
}
function closeItemModal() { $('#item-mask').hidden = true; }

/* ---------- Con 记忆区（M4） ---------- */
function fillConGroupFilters(cons) {
  const wrap = $('#con-group-filters');
  const cur = (state.conFilter || {}).group || 'all';
  const groups = [...new Set(cons.map(c => c.group).filter(Boolean))].sort();
  const key = groups.join(',');
  if (wrap.dataset.built === '1' && wrap.dataset.gkey === key) {
    // 只更新 active 态
    $$('#con-group-filters .chip').forEach(x => x.classList.toggle('active', x.dataset.group === cur));
    return;
  }
  wrap.dataset.built = '1'; wrap.dataset.gkey = key;
  wrap.innerHTML = `<button class="chip ${cur === 'all' ? 'active' : ''}" data-group="all">全部</button>` +
    groups.map(g => `<button class="chip ${cur === g ? 'active' : ''}" data-group="${esc(g)}">${esc(g)}</button>`).join('');
}

function renderCons() {
  const fg = (state.conFilter || {}).group || 'all';
  const list = $('#con-list'); list.innerHTML = '';
  const all = state.data.cons || [];
  fillConGroupFilters(all);
  const cons = all
    .filter(c => fg === 'all' || c.group === fg)
    .sort((a, b) => (b.date || '').localeCompare(a.date || ''));
  $('#con-hint').style.display = all.length ? 'none' : 'block';

  cons.forEach(c => {
    const img = c.seatImage
      ? `<div class="cthumb"><span class="cph">演</span><img src="/file/${encodeURIComponent(c.seatImage)}" alt="" onerror="this.remove()"></div>`
      : `<div class="cthumb"><span class="cph">演</span></div>`;
    const price = c.ticketPrice != null ? `<span class="cprice">票 ¥${Number(c.ticketPrice).toLocaleString()}</span>` : '';
    const orig = (c.ticketOriginal && c.ticketOriginal.amount != null)
      ? `<span class="corig">原 ${esc(c.ticketOriginal.currency || '')} ${esc(c.ticketOriginal.amount)}</span>` : '';
    const totalExp = (c.expenses || []).reduce((s, e) => s + (Number(e.amount) || 0), 0);
    const expLine = totalExp > 0 ? `<span class="cexp">花销 ¥${totalExp.toLocaleString()}</span>` : '';
    const mood = c.mood ? `<span class="cmood">${MOOD_STAR[c.mood] || ''}</span>` : '';
    const meta = [c.venue, c.city].filter(Boolean).join(' · ');
    const sub = [c.date, meta, c.seat].filter(Boolean).join(' · ');
    const setN = (c.setlist || []).length;
    const card = document.createElement('div'); card.className = 'con-card';
    card.innerHTML = `
      ${img}
      <div class="ccard-body">
        <div class="ccard-top"><span class="cgroup">${esc(c.group || '未填团体')}</span>${mood}</div>
        <div class="ctitle">${esc(c.title || '未命名')}</div>
        <div class="cmeta">${esc(sub)}</div>
        <div class="cpriceline">${price}${orig}${expLine}</div>
        ${setN ? `<div class="cset">歌单 ${setN} 首</div>` : ''}
        ${c.review ? `<div class="crev">${esc(c.review)}</div>` : ''}
      </div>
      <div class="icard-actions">
        <button class="mini edit" data-id="${esc(c.id)}">编辑</button>
        <button class="mini del" data-id="${esc(c.id)}">删除</button>
      </div>`;
    list.appendChild(card);
  });
}

function addExpRow(wrap, e) {
  const row = document.createElement('div'); row.className = 'exp-row';
  const opts = Object.entries(EXP_LABEL)
    .map(([k, v]) => `<option value="${k}" ${(e && e.type === k) ? 'selected' : ''}>${v}</option>`).join('');
  row.innerHTML = `
    <select class="exp-type">${opts}</select>
    <input class="exp-amt" type="number" min="0" step="0.01" placeholder="CNY" value="${e && e.amount != null ? e.amount : ''}">
    <input class="exp-orig" type="text" placeholder="原币种金额" value="${e && e.originalAmount != null ? esc(e.originalAmount) : ''}">
    <input class="exp-origc" type="text" placeholder="币种" value="${e && e.originalCurrency ? esc(e.originalCurrency) : ''}">
    <input class="exp-note" type="text" placeholder="备注" value="${e && e.note ? esc(e.note) : ''}">
    <button type="button" class="exp-del" title="删除">✕</button>`;
  wrap.appendChild(row);
}
function renderExpRows(wrap, expenses) {
  wrap.innerHTML = '';
  if (!expenses || !expenses.length) { addExpRow(wrap); return; }
  expenses.forEach(e => addExpRow(wrap, e));
}
function readExpRows() {
  const out = [];
  $$('#c-exp-wrap .exp-row').forEach(r => {
    const type = r.querySelector('.exp-type').value;
    const amount = r.querySelector('.exp-amt').value;
    const orig = r.querySelector('.exp-orig').value.trim();
    const origc = r.querySelector('.exp-origc').value.trim();
    const note = r.querySelector('.exp-note').value.trim();
    if (!amount && !orig && !note) return;
    const e = { type: type || 'other' };
    if (amount) e.amount = Number(amount);
    if (orig) e.originalAmount = orig;
    if (origc) e.originalCurrency = origc;
    if (note) e.note = note;
    out.push(e);
  });
  return out;
}

function openConModal(c) {
  $('#con-modal-title').textContent = c ? '编辑 Con 记忆' : '新增 Con 记忆';
  $('#c-id').value = c ? c.id : '';
  $('#c-group').value = (c && c.group) || '';
  $('#c-title').value = (c && c.title) || '';
  $('#c-date').value = (c && c.date) || todayStr();
  $('#c-city').value = (c && c.city) || '';
  $('#c-venue').value = (c && c.venue) || '';
  $('#c-seat').value = (c && c.seat) || '';
  $('#c-price').value = (c && c.ticketPrice != null) ? c.ticketPrice : '';
  $('#c-mood').value = (c && c.mood) ? String(c.mood) : '';
  $('#c-orig').value = (c && c.ticketOriginal && c.ticketOriginal.amount != null) ? c.ticketOriginal.amount : '';
  $('#c-origc').value = (c && c.ticketOriginal && c.ticketOriginal.currency) ? c.ticketOriginal.currency : '';
  $('#c-setlist').value = (c && c.setlist) ? c.setlist.join('\n') : '';
  $('#c-image').value = c ? (c.seatImage || '') : '';
  $('#c-review').value = c ? (c.review || '') : '';
  renderExpRows($('#c-exp-wrap'), c ? (c.expenses || []) : []);
  $('#con-mask').hidden = false;
  $('#c-title').focus();
}
function closeConModal() { $('#con-mask').hidden = true; }

/* ---------- 弹窗（新增 / 编辑 / 从日报预填） ---------- */
function openEventModal(ev, prefill) {
  $('#modal-title').textContent = ev ? '编辑日程' : '新增日程';
  $('#f-id').value = ev ? ev.id : '';
  $('#f-group').value = (prefill && prefill.group) || (ev && ev.group) || '';
  $('#f-type').value = (prefill && prefill.cat) || (ev && ev.type) || 'other';
  $('#f-title').value = (prefill && prefill.title) || (ev && ev.title) || '';
  $('#f-start').value = (prefill && prefill.start) || (ev && ev.startDate) || todayStr();
  $('#f-end').value = (ev && ev.endDate) || '';
  $('#f-location').value = (ev && ev.location) || '';
  $('#f-ticket').value = (ev && ev.ticketStatus) || '';
  $('#f-repeat').value = (ev && ev.repeat) || 'none';
  $('#f-note').value = (ev && ev.note) || '';
  state.prefill = prefill || null;
  $('#modal-mask').hidden = false;
  $('#f-title').focus();
}
function closeModal() { $('#modal-mask').hidden = true; }

/* ---------- 事件绑定 ---------- */
function bindStatic() {
  $$('.tab').forEach(t => t.addEventListener('click', () => {
    $$('.tab').forEach(x => x.classList.remove('active'));
    t.classList.add('active');
    $$('.view').forEach(v => v.classList.remove('active'));
    $('#view-' + t.dataset.view).classList.add('active');
    if (t.dataset.view === 'ledger') renderLedger();
  }));

  $('#btn-add-event').addEventListener('click', () => openEventModal(null, null));
  $('#modal-close').addEventListener('click', closeModal);
  $('#btn-cancel').addEventListener('click', closeModal);
  $('#modal-mask').addEventListener('click', e => { if (e.target === e.currentTarget) closeModal(); });

  /* 收藏区（M3）绑定 */
  $('#btn-add-item').addEventListener('click', () => openItemModal(null));
  $('#item-close').addEventListener('click', closeItemModal);
  $('#i-cancel').addEventListener('click', closeItemModal);
  $('#item-mask').addEventListener('click', e => { if (e.target === e.currentTarget) closeItemModal(); });

  /* Con 记忆区（M4）绑定 */
  $('#btn-add-con').addEventListener('click', () => openConModal(null));
  $('#con-close').addEventListener('click', closeConModal);
  $('#c-cancel').addEventListener('click', closeConModal);
  $('#con-mask').addEventListener('click', e => { if (e.target === e.currentTarget) closeConModal(); });
  $('#c-add-exp').addEventListener('click', () => addExpRow($('#c-exp-wrap')));

  $('#con-form').addEventListener('submit', async e => {
    e.preventDefault();
    const expenses = readExpRows();
    const origAmount = $('#c-orig').value.trim();
    const origCur = $('#c-origc').value.trim();
    const setlistRaw = $('#c-setlist').value.trim();
    const rec = {
      group: $('#c-group').value.trim(),
      title: $('#c-title').value.trim(),
      date: $('#c-date').value,
      city: $('#c-city').value.trim() || undefined,
      venue: $('#c-venue').value.trim() || undefined,
      seat: $('#c-seat').value.trim() || undefined,
      ticketPrice: $('#c-price').value ? Number($('#c-price').value) : undefined,
      mood: $('#c-mood').value ? Number($('#c-mood').value) : undefined,
      expenses: expenses.length ? expenses : undefined,
      setlist: setlistRaw ? setlistRaw.split('\n').map(s => s.trim()).filter(Boolean) : undefined,
      seatImage: $('#c-image').value.trim() || undefined,
      review: $('#c-review').value.trim() || undefined,
    };
    if (origAmount) {
      rec.ticketOriginal = { amount: origAmount };
      if (origCur) rec.ticketOriginal.currency = origCur;
    }
    const id = $('#c-id').value;
    try {
      if (id) {
        await api('/api/cons/' + id, { method: 'PUT', body: JSON.stringify(rec) });
        toast('记忆已更新');
      } else {
        await api('/api/cons', { method: 'POST', body: JSON.stringify(rec) });
        toast('已保存记忆');
      }
      closeConModal(); await refreshData(); renderCons();
    } catch (err) { toast('保存失败：' + err.message); }
  });

  $$('#item-status-filters .chip').forEach(c => c.addEventListener('click', () => {
    $$('#item-status-filters .chip').forEach(x => x.classList.remove('active'));
    c.classList.add('active');
    state.itemFilter.status = c.dataset.status; renderItems();
  }));
  $$('#item-kind-filters .chip').forEach(c => c.addEventListener('click', () => {
    $$('#item-kind-filters .chip').forEach(x => x.classList.remove('active'));
    c.classList.add('active');
    state.itemFilter.kind = c.dataset.kind; renderItems();
  }));

  $('#item-form').addEventListener('submit', async e => {
    e.preventDefault();
    const rec = {
      kind: $('#i-kind').value,
      status: $('#i-status').value,
      group: $('#i-group').value.trim(),
      name: $('#i-name').value.trim(),
      version: $('#i-version').value.trim() || undefined,
      platform: $('#i-platform').value || undefined,
      purchasedDate: $('#i-date').value || undefined,
      amount: $('#i-amount').value ? Number($('#i-amount').value) : undefined,
      originalAmount: $('#i-orig').value ? $('#i-orig').value : undefined,
      originalCurrency: $('#i-origc').value.trim() || undefined,
      image: $('#i-image').value.trim() || undefined,
      note: $('#i-note').value.trim() || undefined,
    };
    if (rec.originalAmount && !rec.originalCurrency) rec.originalCurrency = 'JPY';
    const id = $('#i-id').value;
    try {
      if (id) {
        await api('/api/items/' + id, { method: 'PUT', body: JSON.stringify(rec) });
        toast('收藏已更新');
      } else {
        await api('/api/items', { method: 'POST', body: JSON.stringify(rec) });
        toast('已保存收藏');
      }
      closeItemModal(); await refreshData(); renderItems();
    } catch (err) { toast('保存失败：' + err.message); }
  });

  document.addEventListener('click', async e => {
    const addBtn = e.target.closest('.btn-add-ev');
    if (addBtn) {
      openEventModal(null, {
        group: addBtn.dataset.group,
        cat: inferType(addBtn.dataset.cat, addBtn.dataset.title),
        title: addBtn.dataset.title,
        start: todayStr(),
        id: addBtn.dataset.id,
        url: addBtn.dataset.url,
      });
      return;
    }
    const delBtn = e.target.closest('.evt-del');
    if (delBtn) {
      if (!confirm('删除这条日程？')) return;
      try {
        await api('/api/events/' + delBtn.dataset.id, { method: 'DELETE' });
        await refreshData(); renderEvents(); toast('日程已删除');
      } catch (err) { toast('删除失败：' + err.message); }
    }

    /* Con 记忆区（M4）交互（放在 items 之前，避免 .mini.edit/.mini.del 通用选择器误匹配） */
    const conFilterChip = e.target.closest('#con-group-filters .chip');
    if (conFilterChip) {
      state.conFilter = { group: conFilterChip.dataset.group };
      $$('#con-group-filters .chip').forEach(x => x.classList.remove('active'));
      conFilterChip.classList.add('active');
      renderCons();
      return;
    }
    const editCon = e.target.closest('.con-card .mini.edit');
    if (editCon) {
      const c = (state.data.cons || []).find(x => x.id === editCon.dataset.id);
      if (c) openConModal(c);
      return;
    }
    const delCon = e.target.closest('.con-card .mini.del');
    if (delCon) {
      if (!confirm('删除这条 Con 记忆？')) return;
      try {
        await api('/api/cons/' + delCon.dataset.id, { method: 'DELETE' });
        await refreshData(); renderCons(); toast('记忆已删除');
      } catch (err) { toast('删除失败：' + err.message); }
    }
    const expDel = e.target.closest('.exp-del');
    if (expDel) { expDel.closest('.exp-row').remove(); return; }

    const editItem = e.target.closest('.mini.edit');
    if (editItem) {
      const it = (state.data.items || []).find(x => x.id === editItem.dataset.id);
      if (it) openItemModal(it);
      return;
    }
    const delItem = e.target.closest('.mini.del');
    if (delItem) {
      if (!confirm('删除这条收藏？')) return;
      try {
        await api('/api/items/' + delItem.dataset.id, { method: 'DELETE' });
        await refreshData(); renderItems(); toast('收藏已删除');
      } catch (err) { toast('删除失败：' + err.message); }
    }
  });

  $('#event-form').addEventListener('submit', async e => {
    e.preventDefault();
    const rec = {
      group: $('#f-group').value.trim(),
      type: $('#f-type').value,
      title: $('#f-title').value.trim(),
      startDate: $('#f-start').value,
      endDate: $('#f-end').value || undefined,
      location: $('#f-location').value.trim() || undefined,
      ticketStatus: $('#f-ticket').value || undefined,
      repeat: $('#f-repeat').value,
      note: $('#f-note').value.trim() || undefined,
    };
    if (state.prefill && state.prefill.id) {
      rec.source = { type: 'daily', itemId: state.prefill.id, url: state.prefill.url, date: state.dailyDate };
    }
    const id = $('#f-id').value;
    try {
      if (id) {
        await api('/api/events/' + id, { method: 'PUT', body: JSON.stringify(rec) });
        toast('日程已更新');
      } else {
        await api('/api/events', { method: 'POST', body: JSON.stringify(rec) });
        toast('已加入日程');
      }
      closeModal(); await refreshData(); renderEvents();
    } catch (err) { toast('保存失败：' + err.message); }
  });
}

const CAT_COLOR = {
  '演出票': '#8d7bb8', '交通': '#c98ba6', '住宿': '#6f9e93', '餐饮': '#e0b27a',
  '周边': '#9aa7d6', '专辑周边': '#c9a3c9', '其他': '#b0a89c'
};
const CAT_ORDER = ['演出票', '交通', '住宿', '餐饮', '周边', '专辑周边', '其他'];

async function renderLedger() {
  const root = $('#ledger-root');
  if (!root) return;
  let stats;
  try { stats = await api('/api/stats'); }
  catch (e) {
    root.innerHTML = `<div class="placeholder card"><h3>账本统计</h3><p>加载失败：${esc(e.message)}</p></div>`;
    return;
  }
  const budget = (state.data && state.data.profile && state.data.profile.budget) || { year: new Date().getFullYear(), limit: 0 };
  const total = Number(stats.total) || 0;
  const cats = CAT_ORDER.map(c => ({ name: c, val: (stats.byCategory && stats.byCategory[c]) || 0 }))
    .filter(c => c.val > 0).sort((a, b) => b.val - a.val);
  const monthly = stats.monthly || {};
  const yKeys = Object.keys(monthly).filter(k => /^\d{4}-\d{2}$/.test(k)).sort();
  const maxMonth = yKeys.length ? Math.max(...yKeys.map(k => monthly[k])) : 0;
  const thisYear = String(budget.year || new Date().getFullYear());
  const yearSpend = yKeys.filter(k => k.startsWith(thisYear)).reduce((s, k) => s + monthly[k], 0);
  const remain = (budget.limit || 0) - yearSpend;

  // 环形图分段
  let acc = 0; const segs = [];
  cats.forEach(c => {
    const pct = total ? (c.val / total * 100) : 0;
    segs.push(`${CAT_COLOR[c.name]} ${acc.toFixed(2)}% ${(acc + pct).toFixed(2)}%`);
    acc += pct;
  });
  const ring = total ? `conic-gradient(${segs.join(',')})` : 'var(--line)';

  const legend = cats.length ? cats.map(c => {
    const p = total ? Math.round(c.val / total * 100) : 0;
    return `<li><span class="lg-dot" style="background:${CAT_COLOR[c.name]}"></span>` +
      `<span class="lg-name">${esc(c.name)}</span>` +
      `<span class="lg-val">¥${Number(c.val).toLocaleString()}</span>` +
      `<span class="lg-pct">${p}%</span></li>`;
  }).join('') : `<li class="muted">暂无支出</li>`;

  // 月度柱（固定像素高度，最大映射到 150px）
  const BAR_H = 150;
  const bars = yKeys.length ? yKeys.map(k => {
    const v = monthly[k];
    const h = maxMonth ? Math.round(v / maxMonth * BAR_H) : 0;
    return `<div class="bar-col"><div class="bar" style="height:${h}px" title="¥${Number(v).toLocaleString()}"></div>` +
      `<span class="bar-x">${esc(k.slice(2))}</span><span class="bar-v">¥${Number(v).toLocaleString()}</span></div>`;
  }).join('') : `<p class="hint">暂无月度数据</p>`;

  // 年度总结
  let topMonth = '—', topVal = 0;
  yKeys.forEach(k => { if (monthly[k] > topVal) { topVal = monthly[k]; topMonth = k; } });
  const topCat = cats[0];
  const budgetPct = (budget.limit) ? Math.min(100, Math.round(yearSpend / budget.limit * 100)) : 0;

  root.innerHTML = `
    <div class="kpi-row">
      <div class="kpi"><span class="kpi-label">累计总花费</span><span class="kpi-val">¥${Number(total).toLocaleString()}</span></div>
      <div class="kpi"><span class="kpi-label">看过的 Con</span><span class="kpi-val">${stats.conCount || 0} 场</span></div>
      <div class="kpi"><span class="kpi-label">已记录收藏</span><span class="kpi-val">${stats.itemCount || 0} 件</span></div>
    </div>
    <div class="card ledger-donut">
      <div class="card-head"><h3>品类占比</h3></div>
      <div class="donut-wrap">
        <div class="donut" style="background:${ring}"><div class="donut-hole"><span>${total ? '¥' + Number(total).toLocaleString() : '暂无'}</span></div></div>
        <ul class="legend">${legend}</ul>
      </div>
    </div>
    <div class="card ledger-monthly">
      <div class="card-head"><h3>月度花费趋势</h3></div>
      <div class="bars">${bars}</div>
    </div>
    <div class="card ledger-budget">
      <div class="card-head"><h3>年度预算 · ${esc(thisYear)}</h3></div>
      ${budget.limit ? `
        <div class="budget-line"><span>已用 ¥${Number(yearSpend).toLocaleString()}</span><span>预算 ¥${Number(budget.limit).toLocaleString()}</span></div>
        <div class="budget-bar"><div class="budget-fill" style="width:${budgetPct}%"></div></div>
        <p class="muted">${remain >= 0 ? '剩余 ¥' + Number(remain).toLocaleString() : '已超支 ¥' + Number(Math.abs(remain)).toLocaleString()}</p>
      ` : `<p class="muted">未设置年度预算</p>`}
    </div>
    <div class="card ledger-year">
      <div class="card-head"><h3>年度总结 · 截至 ${esc(todayStr())}</h3></div>
      <ul class="year-list">
        <li>累计总花费 <b>¥${Number(total).toLocaleString()}</b></li>
        ${topMonth !== '—' ? `<li>最高消费月 <b>${esc(topMonth)}</b>（¥${Number(topVal).toLocaleString()}）</li>` : ''}
        ${topCat ? `<li>最大支出品类 <b>${esc(topCat.name)}</b>（¥${Number(topCat.val).toLocaleString()}，${Math.round(topCat.val / total * 100)}%）</li>` : ''}
        <li>看过 Con <b>${stats.conCount || 0}</b> 场，已记录收藏 <b>${stats.itemCount || 0}</b> 件</li>
      </ul>
      <p class="muted">* 仅统计 CNY 金额；原币种仅展示不汇总；种草 / 已出物不计入总账。</p>
    </div>`;
}

async function refreshData() { state.data = await api('/api/data'); }

function fillGroupList() {
  const set = new Set();
  (state.data.profile.groups || []).forEach(g => set.add(g));
  (state.daily && state.daily.sections || []).forEach(s =>
    (s.items || []).forEach(it => (it.groups || []).forEach(g => set.add(g))));
  const dl = $('#group-list'); dl.innerHTML = '';
  [...set].sort().forEach(g => {
    const o = document.createElement('option'); o.value = g; dl.appendChild(o);
  });
}

init();
