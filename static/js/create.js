(() => {
  const input = document.getElementById('frame-input');
  const zone = document.getElementById('dropzone');
  const preview = document.getElementById('frame-preview');
  const hint = document.getElementById('dropzone-hint');
  const status = document.getElementById('frame-status');
  const submit = document.getElementById('create-submit');
  const form = document.getElementById('create-form');

  const setStatus = (msg, ok) => { status.textContent = msg; status.className = 'small ' + (ok ? 'ok' : 'err'); };

  function inspect(file) {
    if (!file) return;
    if (file.type !== 'image/png') { setStatus('Please choose a PNG file.', false); submit.disabled = true; return; }
    if (file.size > 10 * 1024 * 1024) { setStatus('Frame must be 10 MB or smaller.', false); submit.disabled = true; return; }
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      preview.src = url; preview.hidden = false; hint.hidden = true;
      const w = img.naturalWidth, h = img.naturalHeight;
      if (Math.min(w, h) < 400) { setStatus(`Frame is ${w}×${h}px — it must be at least 400×400px.`, false); submit.disabled = true; return; }
      if (Math.max(w, h) > 4000) { setStatus(`Frame is ${w}×${h}px — max 4000px per side.`, false); submit.disabled = true; return; }
      const c = document.createElement('canvas');
      const s = Math.min(1, 400 / Math.max(w, h));
      c.width = Math.round(w * s); c.height = Math.round(h * s);
      const ctx = c.getContext('2d');
      ctx.drawImage(img, 0, 0, c.width, c.height);
      const d = ctx.getImageData(0, 0, c.width, c.height).data;
      let transparent = 0;
      for (let i = 3; i < d.length; i += 4) if (d[i] < 250) transparent++;
      const pct = transparent / (d.length / 4) * 100;
      if (pct === 0) { setStatus('This PNG has no transparent area — the photo would be hidden behind it.', false); submit.disabled = true; return; }
      const notes = [`${w}×${h}px`, `${pct.toFixed(0)}% transparent`];
      if (w !== h) notes.push('not square — will still work, but square is recommended');
      setStatus('Looks good: ' + notes.join(' · '), true);
      submit.disabled = false;
    };
    img.onerror = () => setStatus('Could not read that image.', false);
    img.src = url;
  }

  input.addEventListener('change', () => inspect(input.files[0]));
  ['dragenter', 'dragover'].forEach(ev => zone.addEventListener(ev, e => { e.preventDefault(); zone.classList.add('drag'); }));
  ['dragleave', 'drop'].forEach(ev => zone.addEventListener(ev, e => { e.preventDefault(); zone.classList.remove('drag'); }));
  zone.addEventListener('drop', e => {
    const file = e.dataTransfer.files[0];
    if (!file) return;
    const dt = new DataTransfer(); dt.items.add(file); input.files = dt.files;
    inspect(file);
  });
  form.addEventListener('submit', () => { submit.disabled = true; submit.textContent = 'Publishing…'; });
})();
