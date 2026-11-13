/**
 * Nexa Pals sound effects — synthesized with the Web Audio API, so there
 * are no audio files to host or download (matters for South African data
 * costs). Every sound is a couple of short oscillator tones, not a sample.
 *
 * Respects a per-browser mute preference (localStorage) so a student or
 * parent can turn it off — sound defaults ON but is never forced.
 */
(function () {
  let ctx = null;

  function getCtx() {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    if (!ctx) ctx = new AC();
    return ctx;
  }

  function soundEnabled() {
    try {
      const v = localStorage.getItem('nexapals_sound');
      return v === null ? true : v === 'on';
    } catch {
      return true;
    }
  }

  function setSoundEnabled(on) {
    try {
      localStorage.setItem('nexapals_sound', on ? 'on' : 'off');
    } catch {
      /* localStorage unavailable (private mode etc.) — sound just stays default-on for this tab */
    }
  }

  function tone(freq, duration, type, gainLevel, delay) {
    if (!soundEnabled()) return;
    const audioCtx = getCtx();
    if (!audioCtx) return;
    if (audioCtx.state === 'suspended') audioCtx.resume();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = type || 'sine';
    osc.frequency.value = freq;
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    const t0 = audioCtx.currentTime + (delay || 0);
    const g = gainLevel || 0.12;
    gain.gain.setValueAtTime(0.0001, t0);
    gain.gain.exponentialRampToValueAtTime(g, t0 + 0.015);
    gain.gain.exponentialRampToValueAtTime(0.0001, t0 + duration);
    osc.start(t0);
    osc.stop(t0 + duration + 0.02);
  }

  window.NexaSound = {
    enabled: soundEnabled,
    setEnabled: setSoundEnabled,
    click: function () {
      tone(440, 0.05, 'sine', 0.06, 0);
    },
    correct: function () {
      tone(523.25, 0.12, 'sine', 0.12, 0);
      tone(783.99, 0.16, 'sine', 0.1, 0.08);
    },
    wrong: function () {
      tone(196, 0.18, 'sawtooth', 0.07, 0);
    },
    levelUp: function () {
      [523.25, 659.25, 783.99, 1046.5].forEach(function (f, i) {
        tone(f, 0.18, 'sine', 0.12, i * 0.09);
      });
    },
    badge: function () {
      [659.25, 830.61, 987.77].forEach(function (f, i) {
        tone(f, 0.15, 'triangle', 0.1, i * 0.07);
      });
    },
  };
})();
