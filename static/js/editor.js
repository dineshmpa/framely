(() => {
  const cfg = window.FRAMELY;
  const stage = document.getElementById('stage');
  const canvas = document.getElementById('canvas');
  const ctx = canvas.getContext('2d');
  const preview = document.getElementById('preview');
  const pctx = preview.getContext('2d');
  const fileInput = document.getElementById('photo-input');
  const controls = document.getElementById('controls');
  const help = document.getElementById('stage-help');
  const zoomEl = document.getElementById('zoom');
  const rotEl = document.getElementById('rotate');
  const bgEl = document.getElementById('bg');
  const downloadBtn = document.getElementById('download');
  const shareBtn = document.getElementById('share-img');
  const W = canvas.width, H = canvas.height;

  const frame = new Image();
  let photo = null;
  const st = { x: W / 2, y: H / 2, scale: 1, base: 1, rot: 0, flip: 1 };

  frame.onload = render;
  frame.src = cfg.frameUrl;

  function render() {
    ctx.clearRect(0, 0, W, H);
    if (photo) {
      ctx.fillStyle = bgEl.value;
      ctx.fillRect(0, 0, W, H);
      ctx.save();
      ctx.translate(st.x, st.y);
      ctx.rotate(st.rot * Math.PI / 180);
      ctx.scale(st.scale * st.flip, st.scale);
      ctx.drawImage(photo, -photo.naturalWidth / 2, -photo.naturalHeight / 2);
      ctx.restore();
    }
    if (frame.complete && frame.naturalWidth) ctx.drawImage(frame, 0, 0, W, H);
    pctx.clearRect(0, 0, preview.width, preview.height);
    const side = Math.min(W, H);
    pctx.drawImage(canvas, (W - side) / 2, (H - side) / 2, side, side, 0, 0, preview.width, preview.height);
  }

  function syncInputs() {
    zoomEl.value = (st.scale / st.base).toFixed(2);
    rotEl.value = Math.round(((st.rot + 540) % 360) - 180);
  }

  function resetPosition() {
    st.base = Math.max(W / photo.naturalWidth, H / photo.naturalHeight);
    st.scale = st.base; st.x = W / 2; st.y = H / 2; st.rot = 0; st.flip = 1;
    syncInputs(); render();
  }

  function loadPhoto(file) {
    if (!file || !file.type.startsWith('image/')) { alert('Please choose an image file.'); return; }
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      if (photo && photo.src.startsWith('blob:')) URL.revokeObjectURL(photo.src);
      photo = img;
      stage.classList.add('has-photo');
      controls.hidden = false; help.hidden = false;
      downloadBtn.disabled = false; shareBtn.disabled = false;
      resetPosition();
    };
    img.onerror = () => alert('Sorry, that image could not be loaded. Try a JPG or PNG.');
    img.src = url;
  }

  const openPicker = () => fileInput.click();
  document.getElementById('stage-cta').addEventListener('click', openPicker);
  document.getElementById('change').addEventListener('click', openPicker);
  fileInput.addEventListener('change', () => { loadPhoto(fileInput.files[0]); fileInput.value = ''; });

  ['dragenter', 'dragover'].forEach(ev => stage.addEventListener(ev, e => { e.preventDefault(); stage.classList.add('drag-over'); }));
  ['dragleave', 'drop'].forEach(ev => stage.addEventListener(ev, e => { e.preventDefault(); stage.classList.remove('drag-over'); }));
  stage.addEventListener('drop', e => loadPhoto(e.dataTransfer.files[0]));

  // Pointer interactions: 1 pointer = drag, 2 pointers = pinch zoom + rotate
  const toCanvas = (cx, cy) => {
    const r = canvas.getBoundingClientRect();
    return { x: (cx - r.left) * W / r.width, y: (cy - r.top) * H / r.height };
  };
  const pointers = new Map();
  let gesture = null;

  function startGesture() {
    const pts = [...pointers.values()];
    if (pts.length === 1) {
      gesture = { type: 'drag', start: pts[0], x: st.x, y: st.y };
    } else if (pts.length >= 2) {
      const [a, b] = pts;
      gesture = {
        type: 'pinch',
        dist: Math.hypot(b.x - a.x, b.y - a.y) || 1,
        angle: Math.atan2(b.y - a.y, b.x - a.x),
        mid: { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 },
        x: st.x, y: st.y, scale: st.scale, rot: st.rot,
      };
    } else gesture = null;
  }

  canvas.addEventListener('pointerdown', e => {
    if (!photo) { openPicker(); return; }
    canvas.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId, toCanvas(e.clientX, e.clientY));
    stage.classList.add('dragging');
    startGesture();
  });
  canvas.addEventListener('pointermove', e => {
    if (!pointers.has(e.pointerId) || !gesture) return;
    pointers.set(e.pointerId, toCanvas(e.clientX, e.clientY));
    const pts = [...pointers.values()];
    if (gesture.type === 'drag') {
      st.x = gesture.x + pts[0].x - gesture.start.x;
      st.y = gesture.y + pts[0].y - gesture.start.y;
    } else if (pts.length >= 2) {
      const [a, b] = pts;
      const dist = Math.hypot(b.x - a.x, b.y - a.y);
      const angle = Math.atan2(b.y - a.y, b.x - a.x);
      const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
      const k = dist / gesture.dist;
      st.scale = clampScale(gesture.scale * k);
      const realK = st.scale / gesture.scale;
      const dRot = angle - gesture.angle;
      // Rotate/scale photo center around the gesture midpoint
      const ox = gesture.x - gesture.mid.x, oy = gesture.y - gesture.mid.y;
      const cos = Math.cos(dRot), sin = Math.sin(dRot);
      st.x = mid.x + (ox * cos - oy * sin) * realK;
      st.y = mid.y + (ox * sin + oy * cos) * realK;
      st.rot = gesture.rot + dRot * 180 / Math.PI;
    }
    syncInputs(); render();
  });
  const endPointer = e => {
    pointers.delete(e.pointerId);
    if (!pointers.size) stage.classList.remove('dragging');
    startGesture();
  };
  canvas.addEventListener('pointerup', endPointer);
  canvas.addEventListener('pointercancel', endPointer);

  const clampScale = s => Math.min(st.base * 5, Math.max(st.base * 0.1, s));

  function zoomAt(newScale, px, py) {
    const s = clampScale(newScale);
    const k = s / st.scale;
    st.x = px - (px - st.x) * k;
    st.y = py - (py - st.y) * k;
    st.scale = s;
    syncInputs(); render();
  }

  canvas.addEventListener('wheel', e => {
    if (!photo) return;
    e.preventDefault();
    const p = toCanvas(e.clientX, e.clientY);
    zoomAt(st.scale * Math.exp(-e.deltaY * 0.0015), p.x, p.y);
  }, { passive: false });

  zoomEl.addEventListener('input', () => { if (photo) zoomAt(st.base * parseFloat(zoomEl.value), W / 2, H / 2); });
  rotEl.addEventListener('input', () => { st.rot = parseFloat(rotEl.value); render(); });
  bgEl.addEventListener('input', render);
  document.getElementById('flip').addEventListener('click', () => { st.flip *= -1; render(); });
  document.getElementById('reset').addEventListener('click', () => photo && resetPosition());

  // Keyboard nudging for accessibility
  canvas.tabIndex = 0;
  canvas.addEventListener('keydown', e => {
    if (!photo) return;
    const step = e.shiftKey ? 20 : 5;
    const map = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
    if (map[e.key]) { st.x += map[e.key][0]; st.y += map[e.key][1]; render(); e.preventDefault(); }
    else if (e.key === '+' || e.key === '=') zoomAt(st.scale * 1.05, W / 2, H / 2);
    else if (e.key === '-') zoomAt(st.scale / 1.05, W / 2, H / 2);
  });

  const toBlob = () => new Promise(res => canvas.toBlob(res, 'image/png'));
  const fileName = () => `${cfg.slug}-framely.png`;

  function recordUse() {
    fetch(cfg.useUrl, { method: 'POST' })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) document.getElementById('uses').textContent = d.uses; })
      .catch(() => {});
  }

  downloadBtn.addEventListener('click', async () => {
    if (!photo) return;
    render();
    const blob = await toBlob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = fileName();
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    recordUse();
  });

  if (navigator.canShare && navigator.canShare({ files: [new File([''], 'x.png', { type: 'image/png' })] })) {
    shareBtn.hidden = false;
    shareBtn.addEventListener('click', async () => {
      const file = new File([await toBlob()], fileName(), { type: 'image/png' });
      try {
        await navigator.share({ files: [file], title: cfg.title, text: `${cfg.title} ${cfg.link}` });
        recordUse();
      } catch (e) { /* user cancelled */ }
    });
  }

  document.getElementById('copy-link').addEventListener('click', async e => {
    try { await navigator.clipboard.writeText(cfg.link); }
    catch (err) { prompt('Copy this link:', cfg.link); return; }
    e.target.textContent = 'Link copied!';
    setTimeout(() => (e.target.textContent = 'Copy campaign link'), 1500);
  });
})();
