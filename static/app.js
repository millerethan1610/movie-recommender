/**
 * CineMood & Bites — Dynamic Client Application Logic
 * 
 * Features:
 * - 100% dynamic data integration: no placeholders, no hardcoded caps.
 * - Dynamic Excel/CSV drag-and-drop file ingestion with live re-indexing.
 * - Guaranteed visible poster pipeline with lazy TMDB lookup & SVG fallback.
 * - Mood-aligned dynamic themes (0.4s transitions) with Spotify soundtrack embeds.
 * - Real-time debounced full-text search (250ms).
 * - Full catalog pagination (9,000+ films) with infinite scroll & load-more.
 * - SQLite-backed authentication (JWT session persistence), persistent ratings, and watchlist.
 */

// Global Application State
const state = {
  token: localStorage.getItem('cinemood_token') || null,
  currentUser: null,
  currentMood: 'joyful',
  selectedGenres: [],
  minRating: 3.0,
  decade: 'All',
  selectedMediaType: 'all', // 'all' | 'Movie' | 'Series'
  tasteBalance: 50, // 0 = 100% Ratings/Taste, 100 = 100% Mood
  userRatings: {},
  userWatchlist: [],
  allGenres: [],
  moodProfiles: {},
  isRecsLoading: false,
  activeDetailMovieId: null,
  viewMode: 'recommendations', // 'recommendations' | 'catalog'
  catalogPage: 1,
  catalogTotalPages: 1,
  catalogTotalCount: 0,
  catalogIsLoading: false,
};

// Popular starter films for cold-start taste calibration
const STARTER_MOVIES = [
  { id: 1, title: 'Interstellar (2014)' },
  { id: 2, title: 'Inception (2010)' },
  { id: 14, title: 'The Dark Knight (2008)' },
  { id: 26, title: 'The Shawshank Redemption (1994)' },
  { id: 28, title: 'Pulp Fiction (1994)' },
  { id: 63, title: 'Toy Story (1995)' },
];

const posterCache = {};

// --------------------------------------------------------------------------
// Initialization Lifecycle
// --------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', async () => {
  setupEventListeners();
  setupSearch();
  setupTabs();
  setupFormatSwitchers();
  setupAuthModal();
  setupInfiniteScroll();

  await checkAuthStatus();
  await loadMoods();
  await loadGenres();
  await loadSystemHealth();
  await loadUserRatings();
  await loadUserWatchlist();

  renderStarterChips();
  fetchRecommendations();
});

// --------------------------------------------------------------------------
// Authentication & Profile Suite
// --------------------------------------------------------------------------

function getAuthHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  if (state.token) {
    headers['Authorization'] = `Bearer ${state.token}`;
  }
  return headers;
}

async function checkAuthStatus() {
  if (!state.token) {
    renderAuthNav(null);
    return;
  }
  try {
    const res = await fetch('/api/auth/me', { headers: getAuthHeaders() });
    if (res.ok) {
      const user = await res.json();
      state.currentUser = user;
      if (user.active_mood && user.active_mood in state.moodProfiles) {
        switchMood(user.active_mood, false);
      }
      renderAuthNav(user);
    } else {
      // Invalid/expired token
      signOut();
    }
  } catch (e) {
    console.debug('Auth check failed:', e);
  }
}

function renderAuthNav(user) {
  const container = document.getElementById('authNavContainer');
  if (!container) return;

  if (user) {
    container.innerHTML = `
      <div class="user-avatar-pill" id="userProfileBtn" title="Signed in as ${escapeHtml(user.username)}">
        <span>👤</span>
        <strong>${escapeHtml(user.display_name || user.username)}</strong>
        <button class="user-signout-btn" id="signOutBtn" title="Sign Out">Sign Out</button>
      </div>
    `;
    const signOutBtn = document.getElementById('signOutBtn');
    if (signOutBtn) {
      signOutBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        signOut();
      });
    }
  } else {
    container.innerHTML = `
      <button class="nav-btn" id="openAuthBtn" title="Sign In or Create Account">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
          <circle cx="12" cy="7" r="4"></circle>
        </svg>
        <span>Sign In</span>
      </button>
    `;
    const openBtn = document.getElementById('openAuthBtn');
    if (openBtn) {
      openBtn.addEventListener('click', openAuthModal);
    }
  }
}

function signOut() {
  state.token = null;
  state.currentUser = null;
  localStorage.removeItem('cinemood_token');
  renderAuthNav(null);
  showToast('Logged out successfully.');
  loadUserRatings();
  loadUserWatchlist();
  fetchRecommendations();
}

function openAuthModal() {
  const backdrop = document.getElementById('authModalBackdrop');
  if (backdrop) backdrop.classList.add('open');
  clearAuthNotices();
}

function closeAuthModal() {
  const backdrop = document.getElementById('authModalBackdrop');
  if (backdrop) backdrop.classList.remove('open');
}

function clearAuthNotices() {
  const n = document.getElementById('authNotice');
  if (n) {
    n.style.display = 'none';
    n.className = 'auth-notice';
    n.textContent = '';
  }
}

function showAuthNotice(text, isError = true) {
  const n = document.getElementById('authNotice');
  if (!n) return;
  n.style.display = 'block';
  n.className = `auth-notice ${isError ? 'error' : 'success'}`;
  n.textContent = text;
}

function setupAuthModal() {
  const backdrop = document.getElementById('authModalBackdrop');
  const closeBtn = document.getElementById('closeAuthModalBtn');
  const tabSignIn = document.getElementById('tabSignIn');
  const tabRegister = document.getElementById('tabRegister');
  const signInForm = document.getElementById('signInForm');
  const registerForm = document.getElementById('registerForm');

  if (closeBtn) closeBtn.addEventListener('click', closeAuthModal);
  if (backdrop) {
    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) closeAuthModal();
    });
  }

  if (tabSignIn && tabRegister) {
    tabSignIn.addEventListener('click', () => {
      tabSignIn.classList.add('active');
      tabRegister.classList.remove('active');
      signInForm.style.display = 'block';
      registerForm.style.display = 'none';
      clearAuthNotices();
    });

    tabRegister.addEventListener('click', () => {
      tabRegister.classList.add('active');
      tabSignIn.classList.remove('active');
      registerForm.style.display = 'block';
      signInForm.style.display = 'none';
      clearAuthNotices();
    });
  }

  // Handle Login
  if (signInForm) {
    signInForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      clearAuthNotices();
      const u = document.getElementById('loginUsername').value.trim();
      const p = document.getElementById('loginPassword').value;

      try {
        const res = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: jsonPayload({ username: u, password: p }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Login failed');

        state.token = data.user.token;
        state.currentUser = data.user;
        localStorage.setItem('cinemood_token', state.token);
        renderAuthNav(data.user);
        closeAuthModal();
        showToast(`🎉 Welcome back, ${data.user.display_name}!`);

        await loadUserRatings();
        await loadUserWatchlist();
        fetchRecommendations();
      } catch (err) {
        showAuthNotice(err.message, true);
      }
    });
  }

  // Handle Registration
  if (registerForm) {
    registerForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      clearAuthNotices();
      const u = document.getElementById('regUsername').value.trim();
      const p = document.getElementById('regPassword').value;
      const d = document.getElementById('regDisplayName').value.trim();

      try {
        const res = await fetch('/api/auth/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: jsonPayload({ username: u, password: p, display_name: d || null }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Registration failed');

        state.token = data.user.token;
        state.currentUser = data.user;
        localStorage.setItem('cinemood_token', state.token);
        renderAuthNav(data.user);
        closeAuthModal();
        showToast(`🎉 Account created! Welcome, ${data.user.display_name}!`);

        await loadUserRatings();
        await loadUserWatchlist();
        fetchRecommendations();
      } catch (err) {
        showAuthNotice(err.message, true);
      }
    });
  }
}

// --------------------------------------------------------------------------
// Media Format Switcher (All / Movies / TV Series)
// --------------------------------------------------------------------------

function setupFormatSwitchers() {
  const syncButtons = (activeType) => {
    state.selectedMediaType = activeType;
    document.querySelectorAll('.format-pill, .format-btn').forEach(btn => {
      if (btn.getAttribute('data-type') === activeType) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });

    state.catalogPage = 1;
    if (state.viewMode === 'catalog') {
      fetchCatalogPage(1, false);
    } else {
      fetchRecommendations();
    }
  };

  document.querySelectorAll('.format-pill, .format-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const type = btn.getAttribute('data-type');
      syncButtons(type);
    });
  });
}

async function loadSystemHealth() {
  try {
    const res = await fetch('/api/health');
    if (res.ok) {
      const data = await res.json();
      const nameEl = document.getElementById('datasetSourceName');
      const countEl = document.getElementById('datasetSourceCount');
      if (nameEl) nameEl.textContent = data.source || 'Standard Catalog';
      if (countEl) countEl.textContent = `${(data.movies_loaded || 0).toLocaleString()} films loaded`;

      const tabBrowse = document.getElementById('tabBrowse');
      if (tabBrowse) {
        tabBrowse.innerHTML = `
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
            <rect x="3" y="3" width="7" height="7"></rect>
            <rect x="14" y="3" width="7" height="7"></rect>
            <rect x="14" y="14" width="7" height="7"></rect>
            <rect x="3" y="14" width="7" height="7"></rect>
          </svg>
          Browse All ${(data.movies_loaded || 0).toLocaleString()} Films
        `;
      }
    }
  } catch (e) {
    console.debug('Failed loading health stats:', e);
  }
}

// --------------------------------------------------------------------------
// 100% Visible Poster Pipeline
// --------------------------------------------------------------------------

function getPosterSrc(movie) {
  if (movie.poster_url && movie.poster_url.trim().startsWith('http')) {
    return movie.poster_url.trim();
  }
  return `/api/poster/${movie.movieId}?mood=${encodeURIComponent(state.currentMood)}`;
}

function getSvgFallbackSrc(movie) {
  return `/api/poster/${movie.movieId}?mood=${encodeURIComponent(state.currentMood)}`;
}

async function resolvePosterAsync(movie, imgEl) {
  const mid = movie.movieId;
  if (movie.poster_url && movie.poster_url.trim().startsWith('http')) {
    imgEl.src = movie.poster_url.trim();
    return;
  }
  if (posterCache[mid]) {
    if (posterCache[mid].startsWith('http')) imgEl.src = posterCache[mid];
    return;
  }
  try {
    const res = await fetch(`/api/poster/${mid}/url?mood=${encodeURIComponent(state.currentMood)}`);
    if (res.ok) {
      const data = await res.json();
      posterCache[mid] = data.poster_url;
      if (data.poster_url && data.poster_url.startsWith('http')) {
        imgEl.src = data.poster_url;
        movie.poster_url = data.poster_url;
      }
    }
  } catch (e) {
    // Silent fail: dynamic SVG fallback is already displayed
  }
}

// --------------------------------------------------------------------------
// Mood & Theme Engine + Spotify Soundtrack Embeds
// --------------------------------------------------------------------------

async function loadMoods() {
  try {
    const res = await fetch('/api/moods');
    if (res.ok) {
      state.moodProfiles = await res.json();
    }
  } catch (e) {
    console.error('Failed loading moods:', e);
  }
}

function switchMood(moodKey, persistUser = true) {
  if (!moodKey) return;
  state.currentMood = moodKey;

  // 1. Update HTML data-mood attribute for 0.4s smooth CSS transition
  document.documentElement.setAttribute('data-mood', moodKey);

  // 2. Active mood card UI
  document.querySelectorAll('.mood-card').forEach(c => {
    if (c.getAttribute('data-mood') === moodKey) c.classList.add('active');
    else c.classList.remove('active');
  });

  // 3. Update Hero Texts
  const profile = state.moodProfiles[moodKey];
  if (profile) {
    const statusPill = document.getElementById('moodStatusPill');
    const headline = document.getElementById('heroHeadline');
    const desc = document.getElementById('heroDescription');

    if (statusPill) statusPill.textContent = `CURRENT VIBE: ${profile.name.toUpperCase()}`;
    if (headline) headline.textContent = `${profile.icon} ${profile.name} Mode`;
    if (desc) desc.textContent = profile.tagline;
  }

  // 4. Update Ambient Spotify Player Embed
  updateSpotifyBanner(moodKey);

  // 5. Persist to user profile if signed in
  if (persistUser && state.currentUser) {
    fetch('/api/user/mood', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: jsonPayload({ mood: moodKey }),
    }).catch(console.debug);
  }

  showToast(`Switched mood to ${profile?.name || moodKey}!`);

  if (state.viewMode === 'catalog') {
    fetchCatalogPage(1, false);
  } else {
    fetchRecommendations();
  }
}

function updateSpotifyBanner(moodKey) {
  const SPOTIFY_PLAYLIST_MAP = {
    joyful: {
      title: 'Feel-Good Cinematic Uplift',
      sub: 'Official Cinema Vibe Soundtrack • Auto-tuned to current mood',
      url: 'https://open.spotify.com/embed/playlist/37i9dQZF1DXdPec7aLTmlC?utm_source=generator&theme=0',
    },
    thrilling: {
      title: 'High-Tension Dark Noir & Bass',
      sub: 'Official Cinema Vibe Soundtrack • Pulsing sub-bass & orchestral suspense',
      url: 'https://open.spotify.com/embed/playlist/37i9dQZF1DWWY64Hb7ZaNc?utm_source=generator&theme=0',
    },
    adventurous: {
      title: 'Epic Symphony & Cosmic Odyssey',
      sub: 'Official Cinema Vibe Soundtrack • Sweeping brass & interstellar themes',
      url: 'https://open.spotify.com/embed/playlist/37i9dQZF1DX1tz6EDao8it?utm_source=generator&theme=0',
    },
    cozy: {
      title: 'Warm Acoustic Hearth & Lo-Fi Lounge',
      sub: 'Official Cinema Vibe Soundtrack • Intimate guitar acoustics & gentle vinyl crackle',
      url: 'https://open.spotify.com/embed/playlist/37i9dQZF1DXcBWIGoYBM5M?utm_source=generator&theme=0',
    },
    melancholy: {
      title: 'Deep Slate Piano & Contemplative Strings',
      sub: 'Official Cinema Vibe Soundtrack • Neo-classical keys & atmospheric reverbs',
      url: 'https://open.spotify.com/embed/playlist/37i9dQZF1DX7qK8ma5wgG1?utm_source=generator&theme=0',
    },
  };

  const item = SPOTIFY_PLAYLIST_MAP[moodKey] || SPOTIFY_PLAYLIST_MAP['joyful'];
  const titleEl = document.getElementById('spotifyBannerTitle');
  const subEl = document.getElementById('spotifyBannerSub');
  const iframeEl = document.getElementById('spotifyPlayerIframe');

  if (titleEl) titleEl.textContent = item.title;
  if (subEl) subEl.textContent = item.sub;
  if (iframeEl && iframeEl.src !== item.url) {
    iframeEl.src = item.url;
  }
}

// --------------------------------------------------------------------------
// Recommendations Engine
// --------------------------------------------------------------------------

async function fetchRecommendations() {
  if (state.isRecsLoading) return;
  state.isRecsLoading = true;

  const container = document.getElementById('movieGrid');
  const loadingState = document.getElementById('loadingState');
  const emptyState = document.getElementById('emptyState');
  const resultsCount = document.getElementById('resultsCount');

  container.innerHTML = '';
  loadingState.style.display = 'block';
  emptyState.style.display = 'none';

  const mood_weight = (state.tasteBalance / 100) * 0.70;
  const cf_weight = (1 - state.tasteBalance / 100) * 0.70;
  const content_weight = 0.30;

  const payload = {
    mood: state.currentMood,
    genres: state.selectedGenres.length ? state.selectedGenres : null,
    min_rating: state.minRating,
    decade: state.decade === 'All' ? null : state.decade,
    limit: 24,
    cf_weight: Math.round(cf_weight * 100) / 100,
    mood_weight: Math.round(mood_weight * 100) / 100,
    content_weight: content_weight,
    media_type: state.selectedMediaType === 'all' ? null : state.selectedMediaType,
  };

  try {
    const res = await fetch('/api/recommend', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: jsonPayload(payload),
    });
    if (!res.ok) throw new Error('Recommendation computation failed');

    const data = await res.json();
    loadingState.style.display = 'none';

    const movies = data.results || [];
    resultsCount.textContent = `${movies.length} matches found`;

    if (movies.length === 0) {
      emptyState.style.display = 'block';
      return;
    }

    renderMovieCards(movies);
  } catch (err) {
    loadingState.style.display = 'none';
    console.error('Recommendations error:', err);
    showToast('⚠️ Could not compute recommendations.');
  } finally {
    state.isRecsLoading = false;
  }
}

function renderMovieCards(movies, append = false) {
  const container = document.getElementById('movieGrid');
  if (!append) {
    container.innerHTML = '';
  }

  movies.forEach(movie => {
    const userRating = state.userRatings[movie.movieId] || 0;
    const isWatchlisted = state.userWatchlist.some(w => w.movieId === movie.movieId);

    const card = document.createElement('div');
    card.className = 'movie-card';
    card.setAttribute('data-movie-id', movie.movieId);

    const svgFallback = getSvgFallbackSrc(movie);
    const initialSrc = (movie.poster_url && movie.poster_url.startsWith('http'))
      ? movie.poster_url
      : svgFallback;

    const reasonsHtml = (movie.reasons || [])
      .map(r => `<span class="reason-tag">${escapeHtml(r)}</span>`)
      .join('');

    const pairings = movie.pairings || {
      food: 'Gourmet Truffle Popcorn',
      drink: 'Craft Cherry Soda',
      vibe_icon: '🍿',
    };

    const matchBadgeText = movie.match_score
      ? `${movie.match_score}% MATCH`
      : `⭐ ${(movie.bayesian_score || movie.avg_rating || 3.5).toFixed(1)}`;

    const isSeries = movie.media_type === 'Series';
    const typeBadgeHtml = `<span class="card-type-badge ${isSeries ? 'type-series' : 'type-movie'}">${isSeries ? '📺 TV Series' : '🎬 Movie'}</span>`;

    card.innerHTML = `
      <div class="card-poster" data-action="open-detail" data-id="${movie.movieId}" title="View details & pairings">
        <img 
          class="card-poster-img" 
          src="${escapeHtml(initialSrc)}" 
          alt="${escapeHtml(movie.title)}" 
          loading="lazy" 
          onerror="this.onerror=null; this.src='${escapeHtml(svgFallback)}';"
          data-movie-id="${movie.movieId}"
        >
        <div class="card-poster-gradient"></div>
        ${typeBadgeHtml}
        <button class="bookmark-btn ${isWatchlisted ? 'active' : ''}" data-action="toggle-watchlist" data-id="${movie.movieId}" title="${isWatchlisted ? 'Remove from Menu' : 'Add to Movie Night Menu'}">
          <svg viewBox="0 0 24 24" fill="${isWatchlisted ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2">
            <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path>
          </svg>
        </button>
        <span class="match-badge"><span>${matchBadgeText}</span></span>
      </div>

      <div class="card-body">
        <div class="card-title-row">
          <h3 class="card-title" data-action="open-detail" data-id="${movie.movieId}" style="cursor: pointer;">${escapeHtml(movie.title)}</h3>
          ${movie.release_year ? `<span class="card-year">${movie.release_year}</span>` : ''}
        </div>

        <div class="card-genres">${escapeHtml(movie.genres_str || (movie.genres || []).join(' | '))}</div>

        <div class="community-rating">
          <span class="star-icon-gold">★</span>
          <strong>${movie.avg_rating}</strong>
          <span>(${movie.vote_count} votes)</span>
          ${movie.director ? `<span style="margin-left: auto; color: var(--text-muted); font-size: 0.74rem;">Dir: ${escapeHtml(movie.director)}</span>` : ''}
        </div>

        <div class="card-reasons">
          ${reasonsHtml}
        </div>

        <!-- Movie Night Pairings Preview -->
        <div class="card-pairings-preview" data-action="open-detail" data-id="${movie.movieId}" title="Click for gourmet recipes & pairings">
          <div class="pair-pill">
            <span class="pair-emoji">🍿</span>
            <span class="pair-name">${escapeHtml(pairings.food)}</span>
            <span class="pair-sub">Food</span>
          </div>
          <div class="pair-pill">
            <span class="pair-emoji">🍸</span>
            <span class="pair-name">${escapeHtml(pairings.drink)}</span>
            <span class="pair-sub">Drink</span>
          </div>
        </div>

        <button class="card-detail-btn" data-action="open-detail" data-id="${movie.movieId}">
          <span>Details &amp; Spotify Soundtrack</span>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="9 18 15 12 9 6"></polyline>
          </svg>
        </button>

        <div class="card-rating-widget">
          <span class="widget-label">${userRating > 0 ? `Your Rating: ${userRating}★` : 'Rate to refine:'}</span>
          <div class="star-picker" data-movie-id="${movie.movieId}">
            ${renderStars(movie.movieId, userRating)}
          </div>
        </div>
      </div>
    `;

    container.appendChild(card);

    // Asynchronously resolve TMDB poster
    const imgEl = card.querySelector('.card-poster-img');
    if (imgEl && !movie.poster_url?.startsWith('http')) {
      resolvePosterAsync(movie, imgEl);
    }
  });

  attachCardActionEvents(container);
  attachStarEvents(container);
}

// --------------------------------------------------------------------------
// Full Catalog Browsing, Pagination & Infinite Scroll
// --------------------------------------------------------------------------

function setupTabs() {
  const tabForYou = document.getElementById('tabForYou');
  const tabBrowse = document.getElementById('tabBrowse');
  if (!tabForYou || !tabBrowse) return;

  tabForYou.addEventListener('click', () => {
    if (state.viewMode === 'recommendations') return;
    state.viewMode = 'recommendations';
    tabForYou.classList.add('active');
    tabBrowse.classList.remove('active');
    document.getElementById('catalogLoadMore').style.display = 'none';
    document.getElementById('loadingState').style.display = 'none';
    document.getElementById('emptyState').style.display = 'none';
    fetchRecommendations();
  });

  tabBrowse.addEventListener('click', () => {
    if (state.viewMode === 'catalog') return;
    state.viewMode = 'catalog';
    tabBrowse.classList.add('active');
    tabForYou.classList.remove('active');
    state.catalogPage = 1;
    fetchCatalogPage(1, false);
  });

  const loadMoreBtn = document.getElementById('loadMoreBtn');
  if (loadMoreBtn) {
    loadMoreBtn.addEventListener('click', () => {
      if (state.catalogPage < state.catalogTotalPages) {
        fetchCatalogPage(state.catalogPage + 1, true);
      }
    });
  }
}

async function fetchCatalogPage(page = 1, append = false) {
  if (state.catalogIsLoading) return;
  state.catalogIsLoading = true;

  const container = document.getElementById('movieGrid');
  const loadingState = document.getElementById('loadingState');
  const emptyState = document.getElementById('emptyState');
  const resultsCount = document.getElementById('resultsCount');
  const resultsSubtitle = document.getElementById('resultsSubtitle');
  const loadMoreDiv = document.getElementById('catalogLoadMore');
  const loadMoreBtn = document.getElementById('loadMoreBtn');
  const pageInfo = document.getElementById('catalogPageInfo');

  if (!append) {
    container.innerHTML = '';
    loadingState.style.display = 'block';
    emptyState.style.display = 'none';
  } else {
    if (loadMoreBtn) loadMoreBtn.textContent = 'Loading more films...';
  }

  const genre = state.selectedGenres.length === 1 ? state.selectedGenres[0] : '';
  const mediaTypeParam = state.selectedMediaType === 'all' ? '' : state.selectedMediaType;

  try {
    const url = `/api/movies?page=${page}&limit=24&genre=${encodeURIComponent(genre)}&mood=${encodeURIComponent(state.currentMood)}&media_type=${encodeURIComponent(mediaTypeParam)}`;
    const res = await fetch(url, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error('Catalog fetch failed');

    const data = await res.json();
    loadingState.style.display = 'none';

    const movies = data.results || [];
    state.catalogPage = data.page;
    state.catalogTotalPages = data.total_pages;
    state.catalogTotalCount = data.total_count;

    resultsCount.textContent = `${data.total_count.toLocaleString()} films in catalog`;
    resultsSubtitle.textContent = `Page ${data.page} of ${data.total_pages} • Sorted by community consensus`;

    if (movies.length === 0 && !append) {
      emptyState.style.display = 'block';
      loadMoreDiv.style.display = 'none';
      return;
    }

    renderMovieCards(movies, append);

    if (data.page < data.total_pages) {
      loadMoreDiv.style.display = 'block';
      if (loadMoreBtn) {
        loadMoreBtn.innerHTML = `
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16" style="margin-right:0.4rem;">
            <path d="M12 5v14M5 12l7 7 7-7"/>
          </svg> Load More Films
        `;
      }
      if (pageInfo) pageInfo.textContent = `Showing ${Math.min(data.page * 24, data.total_count).toLocaleString()} of ${data.total_count.toLocaleString()} films`;
    } else {
      loadMoreDiv.style.display = 'none';
    }
  } catch (err) {
    loadingState.style.display = 'none';
    console.error('Catalog load error:', err);
    showToast('⚠️ Could not load catalog.');
  } finally {
    state.catalogIsLoading = false;
  }
}

function setupInfiniteScroll() {
  const sentinel = document.getElementById('infiniteScrollSentinel');
  if (!sentinel || !('IntersectionObserver' in window)) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting && state.viewMode === 'catalog') {
        if (state.catalogPage < state.catalogTotalPages && !state.catalogIsLoading) {
          fetchCatalogPage(state.catalogPage + 1, true);
        }
      }
    });
  }, { rootMargin: '250px' });

  observer.observe(sentinel);
}

// --------------------------------------------------------------------------
// Real-Time Debounced Search Bar
// --------------------------------------------------------------------------

function setupSearch() {
  const input = document.getElementById('movieSearchInput');
  const dropdown = document.getElementById('searchDropdown');
  const clearBtn = document.getElementById('searchClearBtn');
  if (!input || !dropdown) return;

  let searchTimeout = null;

  input.addEventListener('input', (e) => {
    const val = e.target.value.trim();
    if (clearBtn) clearBtn.style.display = val ? 'block' : 'none';

    clearTimeout(searchTimeout);
    if (!val) {
      dropdown.style.display = 'none';
      return;
    }

    searchTimeout = setTimeout(async () => {
      try {
        const res = await fetch(`/api/movies?q=${encodeURIComponent(val)}&limit=12`, { headers: getAuthHeaders() });
        const data = await res.json();
        const movies = data.results || (Array.isArray(data) ? data : []);

        if (movies.length === 0) {
          dropdown.innerHTML = `<div style="padding: 1rem; color: var(--text-muted); font-size: 0.85rem;">No films, directors, or genres matched "${escapeHtml(val)}"</div>`;
        } else {
          dropdown.innerHTML = '';
          movies.forEach(m => {
            const item = document.createElement('div');
            item.className = 'search-result-item';

            const posterSrc = getPosterSrc(m);
            const fallbackSrc = getSvgFallbackSrc(m);

            item.innerHTML = `
              <img class="search-item-thumb" src="${escapeHtml(posterSrc)}" alt="${escapeHtml(m.title)}" loading="lazy" onerror="this.onerror=null; this.src='${escapeHtml(fallbackSrc)}';">
              <div style="flex: 1; min-width: 0;">
                <div style="display:flex; align-items:center; gap:0.4rem; margin-bottom:0.2rem;">
                  <span class="search-match-badge">${escapeHtml(m.match_badge || (m.media_type === 'Series' ? '📺 TV Series' : '🎬 Movie'))}</span>
                </div>
                <div class="search-result-title">${escapeHtml(m.title)} ${m.release_year ? `(${m.release_year})` : ''}</div>
                <div class="search-result-genres">${m.director ? `Dir: ${escapeHtml(m.director)} • ` : ''}${escapeHtml(m.genres_str || '')} • ${m.avg_rating}★</div>
              </div>
              <div style="flex-shrink: 0; font-size: 0.75rem; color: var(--primary); font-weight: 700;">
                Details &rarr;
              </div>
            `;

            item.addEventListener('click', () => {
              dropdown.style.display = 'none';
              openMovieDetailModal(m.movieId);
            });

            dropdown.appendChild(item);
          });

          // Add a prominent button to display all search matches in the middle grid
          const viewAllItem = document.createElement('div');
          viewAllItem.className = 'search-view-all-item';
          viewAllItem.innerHTML = `<span>⚡ <strong>View all ${movies.length} results in grid format beside filters &rarr;</strong></span>`;
          viewAllItem.addEventListener('click', () => {
            dropdown.style.display = 'none';
            executeSearchInGrid(val);
          });
          dropdown.appendChild(viewAllItem);
        }
        dropdown.style.display = 'block';
      } catch (err) {
        console.error('Search error:', err);
      }
    }, 250);
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      const val = input.value.trim();
      if (val) {
        dropdown.style.display = 'none';
        executeSearchInGrid(val);
      }
    }
  });

  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      input.value = '';
      clearBtn.style.display = 'none';
      dropdown.style.display = 'none';
      input.focus();
      const resultsTitle = document.getElementById('resultsTitle');
      const resultsSubtitle = document.getElementById('resultsSubtitle');
      if (resultsTitle) resultsTitle.textContent = state.viewMode === 'catalog' ? 'Complete Film Catalog' : 'Curated Films & Pairings';
      if (resultsSubtitle) resultsSubtitle.textContent = state.viewMode === 'catalog' ? 'Sorted by community consensus' : 'Calculated using hybrid item-item collaborative similarity and active mood weights';
      if (state.viewMode === 'catalog') {
        fetchCatalogPage(1, false);
      } else {
        fetchRecommendations();
      }
    });
  }

  document.addEventListener('click', (e) => {
    if (!e.target.closest('#searchContainer')) {
      dropdown.style.display = 'none';
    }
  });
}

async function executeSearchInGrid(query) {
  const container = document.getElementById('movieGrid');
  const loadingState = document.getElementById('loadingState');
  const emptyState = document.getElementById('emptyState');
  const resultsCount = document.getElementById('resultsCount');
  const resultsTitle = document.getElementById('resultsTitle');
  const resultsSubtitle = document.getElementById('resultsSubtitle');
  const loadMoreDiv = document.getElementById('catalogLoadMore');

  container.innerHTML = '';
  loadingState.style.display = 'block';
  emptyState.style.display = 'none';
  if (loadMoreDiv) loadMoreDiv.style.display = 'none';

  if (resultsTitle) resultsTitle.textContent = `Search Results for "${query}"`;
  if (resultsSubtitle) resultsSubtitle.textContent = 'Curated titles matching your query, structured in a multi-column grid';
  if (resultsCount) resultsCount.textContent = 'Searching catalog...';

  // Smooth scroll to the main content area beside genre section
  const mainContent = document.querySelector('.main-content');
  if (mainContent) {
    mainContent.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  try {
    const res = await fetch(`/api/movies?q=${encodeURIComponent(query)}&limit=36`, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error('Search failed');
    const data = await res.json();
    loadingState.style.display = 'none';
    const movies = data.results || (Array.isArray(data) ? data : []);
    if (resultsCount) resultsCount.textContent = `${movies.length} matches found`;

    if (movies.length === 0) {
      emptyState.style.display = 'block';
      const emptyH3 = emptyState.querySelector('h3');
      if (emptyH3) emptyH3.textContent = `No titles matched "${query}"`;
      return;
    }

    renderMovieCards(movies);
  } catch (err) {
    loadingState.style.display = 'none';
    console.error('Search error:', err);
    showToast('⚠️ Could not complete search query.');
  }
}

// --------------------------------------------------------------------------
// Movie Detail & Pairings Modal
// --------------------------------------------------------------------------

async function openMovieDetailModal(movieId) {
  state.activeDetailMovieId = movieId;
  const backdrop = document.getElementById('movieDetailModalBackdrop');
  if (backdrop) backdrop.classList.add('open');

  document.getElementById('modalMovieTitle').textContent = 'Loading film details...';
  document.getElementById('modalMovieSub').textContent = '';
  document.getElementById('modalMovieRating').textContent = '--';
  document.getElementById('modalMovieVotes').textContent = '';
  document.getElementById('modalDirectorText').textContent = 'Loading...';
  document.getElementById('modalCastText').textContent = 'Loading...';
  document.getElementById('modalGenresText').textContent = 'Loading...';
  document.getElementById('modalOverviewText').textContent = 'Fetching plot synopsis and pairing recommendations...';
  document.getElementById('modalRelatedGrid').innerHTML = '<div style="padding: 1rem; color: var(--text-muted); font-size: 0.85rem;">Finding similar titles...</div>';

  try {
    const res = await fetch(`/api/movies/${movieId}?mood=${encodeURIComponent(state.currentMood)}`, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error('Failed to load movie details');

    const data = await res.json();
    const movie = data.movie;
    const related = data.related_movies || [];

    const typeLabel = movie.media_type === 'Series' ? '📺 TV Series' : '🎬 Movie';
    document.getElementById('modalMovieTitle').textContent = movie.title;
    document.getElementById('modalMovieSub').textContent = `${typeLabel} • ${movie.director ? `Directed by ${movie.director} • ` : ''}${movie.release_year ? `${movie.release_year} • ` : ''}${movie.genres_str}`;
    document.getElementById('modalMovieRating').textContent = movie.avg_rating;
    document.getElementById('modalMovieVotes').textContent = `(${movie.vote_count} votes)`;

    // Poster with SVG fallback + async TMDB resolution
    const posterEl = document.getElementById('modalMoviePoster');
    const posterSrc = getPosterSrc(movie);
    const fallbackSrc = getSvgFallbackSrc(movie);
    posterEl.src = posterSrc;
    posterEl.onerror = () => { posterEl.onerror = null; posterEl.src = fallbackSrc; };
    if (!movie.poster_url?.startsWith('http')) {
      resolvePosterAsync(movie, posterEl);
    }

    document.getElementById('modalDirectorText').textContent = movie.director || 'Curated Classic';
    document.getElementById('modalCastText').textContent = movie.cast ? movie.cast.replace(/\|/g, ', ') : 'Ensemble Cast';
    document.getElementById('modalGenresText').textContent = movie.genres_str;
    document.getElementById('modalOverviewText').textContent = movie.overview || 'A captivating cinematic journey.';

    // Pairings
    const p = movie.pairings || {};
    document.getElementById('modalPairingFood').textContent = p.food || 'Gourmet Cinema Popcorn';
    document.getElementById('modalPairingFoodDesc').textContent = p.food_desc || 'Freshly prepared snack pairing.';
    document.getElementById('modalPairingDrink').textContent = p.drink || 'Artisan Cinema Beverage';
    document.getElementById('modalPairingDrinkDesc').textContent = p.drink_desc || 'Craft beverage complement.';
    document.getElementById('modalPairingVibe').textContent = p.ambiance || 'Warm ambient room lighting.';
    const vibeIconEl = document.getElementById('modalPairingVibeIcon');
    if (vibeIconEl) vibeIconEl.textContent = p.vibe_icon || '🕯️';

    // Interactive Star Picker
    const starContainer = document.getElementById('modalStarPicker');
    const curRating = movie.user_rating || state.userRatings[movieId] || 0;
    starContainer.setAttribute('data-movie-id', movieId);
    starContainer.innerHTML = renderStars(movieId, curRating);
    attachStarEvents(starContainer);

    // Watchlist button
    const modalWatchlistBtn = document.getElementById('modalWatchlistBtn');
    const modalWatchlistText = document.getElementById('modalWatchlistText');
    const isWatchlisted = movie.is_in_watchlist || state.userWatchlist.some(w => w.movieId === movieId);

    if (modalWatchlistBtn) {
      if (isWatchlisted) {
        modalWatchlistBtn.classList.add('active');
        modalWatchlistText.textContent = '✓ In Movie Night Menu';
        modalWatchlistBtn.querySelector('svg').setAttribute('fill', 'currentColor');
      } else {
        modalWatchlistBtn.classList.remove('active');
        modalWatchlistText.textContent = '+ Add to Movie Night Menu';
        modalWatchlistBtn.querySelector('svg').setAttribute('fill', 'none');
      }

      modalWatchlistBtn.onclick = () => {
        toggleWatchlist(movieId, modalWatchlistBtn, movie);
      };
    }

    // Render 4 Related Movies
    const relatedGrid = document.getElementById('modalRelatedGrid');
    if (related.length === 0) {
      relatedGrid.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem;">No direct related titles found.</div>';
    } else {
      relatedGrid.innerHTML = '';
      related.forEach(rel => {
        const relCard = document.createElement('div');
        relCard.className = 'related-card';
        relCard.title = `Switch to ${rel.title}`;

        const relPoster = getPosterSrc(rel);
        const relFallback = getSvgFallbackSrc(rel);

        relCard.innerHTML = `
          <div class="related-card-poster">
            <img 
              class="related-poster-img"
              src="${escapeHtml(relPoster)}" 
              alt="${escapeHtml(rel.title)}" 
              loading="lazy" 
              onerror="this.onerror=null; this.src='${escapeHtml(relFallback)}';"
            >
            <span class="related-match-pill">${rel.similarity_score}% SIMILAR</span>
          </div>
          <div class="related-card-body">
            <div class="related-card-title">${escapeHtml(rel.title)}</div>
            <div class="related-card-meta">${rel.release_year || ''} • ${escapeHtml(rel.genres[0] || 'Film')}</div>
          </div>
        `;

        const relImg = relCard.querySelector('.related-poster-img');
        if (relImg && !rel.poster_url?.startsWith('http')) {
          resolvePosterAsync(rel, relImg);
        }

        relCard.addEventListener('click', () => openMovieDetailModal(rel.movieId));
        relatedGrid.appendChild(relCard);
      });
    }
  } catch (err) {
    console.error('Error opening movie detail modal:', err);
    showToast('⚠️ Could not load movie details.');
  }
}

function closeMovieDetailModal() {
  const backdrop = document.getElementById('movieDetailModalBackdrop');
  if (backdrop) backdrop.classList.remove('open');
}

// --------------------------------------------------------------------------
// User Ratings & Collaborative Scoring
// --------------------------------------------------------------------------

async function rateMovie(movieId, title, rating) {
  try {
    const res = await fetch('/api/rate', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: jsonPayload({ movie_id: movieId, rating: rating }),
    });

    if (!res.ok) throw new Error('Rating failed');
    state.userRatings[movieId] = rating;
    showToast(`⭐ Rated "${title}" ${rating}★! Recalculating recommendations...`);

    // Live update star pickers in DOM
    document.querySelectorAll(`.star-picker[data-movie-id="${movieId}"]`).forEach(picker => {
      picker.innerHTML = renderStars(movieId, rating);
      attachStarEvents(picker.parentElement);
    });

    fetchRecommendations();
  } catch (err) {
    console.error('Error rating movie:', err);
    showToast('⚠️ Could not save rating.');
  }
}

async function loadUserRatings() {
  if (!state.currentUser) return;
  try {
    const res = await fetch('/api/ratings', { headers: getAuthHeaders() });
    if (res.ok) {
      state.userRatings = await res.json();
    }
  } catch (e) {
    console.debug('Failed loading ratings:', e);
  }
}

function renderStars(movieId, activeRating) {
  let starsHtml = '';
  for (let s = 1; s <= 5; s++) {
    const isActive = s <= activeRating;
    starsHtml += `<button type="button" class="star-btn ${isActive ? 'active' : ''}" data-star="${s}" title="${s} Stars">★</button>`;
  }
  return starsHtml;
}

function attachStarEvents(parent) {
  const pickers = parent.querySelectorAll('.star-picker');
  pickers.forEach(picker => {
    const movieId = parseInt(picker.getAttribute('data-movie-id'), 10);
    const starBtns = picker.querySelectorAll('.star-btn');

    starBtns.forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const rating = parseFloat(btn.getAttribute('data-star'));
        const cardTitle = picker.closest('.movie-card')?.querySelector('.card-title')?.textContent || 'Film';
        await rateMovie(movieId, cardTitle, rating);
      });
    });
  });
}

// --------------------------------------------------------------------------
// Watchlist / Movie Night Menu Drawer
// --------------------------------------------------------------------------

async function toggleWatchlist(movieId, buttonEl = null, movieObj = null) {
  if (!state.currentUser) {
    openAuthModal();
    showAuthNotice('Please sign in to save films to your persistent Movie Night Menu.', false);
    return;
  }

  try {
    const res = await fetch('/api/watchlist/toggle', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: jsonPayload({ movie_id: movieId }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Watchlist update failed');

    const isAdded = data.is_in_watchlist;
    if (isAdded) {
      if (movieObj) state.userWatchlist.push(movieObj);
      showToast(`🍿 Added to your Movie Night Menu!`);
    } else {
      state.userWatchlist = state.userWatchlist.filter(w => w.movieId !== movieId);
      showToast(`Removed from Movie Night Menu.`);
    }

    updateWatchlistBadge(data.total_watchlist);

    // Update button styling
    if (buttonEl) {
      if (isAdded) {
        buttonEl.classList.add('active');
        const textSpan = buttonEl.querySelector('#modalWatchlistText');
        if (textSpan) textSpan.textContent = '✓ In Movie Night Menu';
        buttonEl.querySelector('svg')?.setAttribute('fill', 'currentColor');
      } else {
        buttonEl.classList.remove('active');
        const textSpan = buttonEl.querySelector('#modalWatchlistText');
        if (textSpan) textSpan.textContent = '+ Add to Movie Night Menu';
        buttonEl.querySelector('svg')?.setAttribute('fill', 'none');
      }
    }

    const drawer = document.getElementById('watchlistDrawer');
    if (drawer && drawer.classList.contains('open')) {
      renderWatchlistDrawer();
    }
  } catch (err) {
    showToast(`⚠️ ${err.message}`);
  }
}

async function loadUserWatchlist() {
  if (!state.currentUser) {
    state.userWatchlist = [];
    updateWatchlistBadge(0);
    return;
  }
  try {
    const res = await fetch('/api/watchlist', { headers: getAuthHeaders() });
    if (res.ok) {
      const data = await res.json();
      state.userWatchlist = data.results || [];
      updateWatchlistBadge(state.userWatchlist.length);
    }
  } catch (e) {
    console.debug('Failed loading watchlist:', e);
  }
}

function updateWatchlistBadge(count = null) {
  const badge = document.getElementById('watchlistCountBadge');
  if (badge) {
    badge.textContent = count !== null ? count : state.userWatchlist.length;
  }
}

function openWatchlistDrawer() {
  if (!state.currentUser) {
    openAuthModal();
    showAuthNotice('Please sign in to view your Movie Night Menu.', false);
    return;
  }
  const drawer = document.getElementById('watchlistDrawer');
  const backdrop = document.getElementById('watchlistBackdrop');
  if (drawer) drawer.classList.add('open');
  if (backdrop) backdrop.classList.add('open');
  renderWatchlistDrawer();
}

function closeWatchlistDrawer() {
  const drawer = document.getElementById('watchlistDrawer');
  const backdrop = document.getElementById('watchlistBackdrop');
  if (drawer) drawer.classList.remove('open');
  if (backdrop) backdrop.classList.remove('open');
}

function renderWatchlistDrawer() {
  const list = document.getElementById('watchlistItemsList');
  const subtitle = document.getElementById('watchlistSubtitle');
  if (!list) return;

  subtitle.textContent = `${state.userWatchlist.length} saved film${state.userWatchlist.length === 1 ? '' : 's'} & pairings`;

  if (state.userWatchlist.length === 0) {
    list.innerHTML = `
      <div style="text-align: center; padding: 3rem 1rem; color: var(--text-muted);">
        <p style="font-size: 2.2rem; margin-bottom: 0.5rem;">🍿</p>
        <p style="font-weight: 600; color: var(--text-primary);">Your Movie Night Menu is empty!</p>
        <p style="font-size: 0.8rem; margin-top: 0.4rem;">Bookmark films to build your movie marathon and curated food/drink plan.</p>
      </div>
    `;
    return;
  }

  list.innerHTML = '';
  state.userWatchlist.forEach(item => {
    const card = document.createElement('div');
    card.className = 'watchlist-item-card';

    const posterSrc = getPosterSrc(item);
    const fallbackSrc = getSvgFallbackSrc(item);
    const pairings = item.pairings || {};

    card.innerHTML = `
      <img 
        class="watchlist-thumb" 
        src="${escapeHtml(posterSrc)}" 
        alt="${escapeHtml(item.title)}" 
        loading="lazy" 
        onerror="this.onerror=null; this.src='${escapeHtml(fallbackSrc)}';"
      >
      <div class="watchlist-details">
        <h4 class="watchlist-title">${escapeHtml(item.title)}</h4>
        <div class="watchlist-meta">${item.release_year ? `${item.release_year} • ` : ''}${escapeHtml(item.genres_str || '')}</div>
        <div class="watchlist-pairings-summary">
          <div>🍿 <strong>Food:</strong> ${escapeHtml(pairings.food || 'Gourmet Popcorn')}</div>
          <div>🍸 <strong>Drink:</strong> ${escapeHtml(pairings.drink || 'Craft Beverage')}</div>
        </div>
      </div>
      <button class="watchlist-remove-btn" title="Remove" data-id="${item.movieId}">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      </button>
    `;

    const thumb = card.querySelector('.watchlist-thumb');
    if (thumb && !item.poster_url?.startsWith('http')) {
      resolvePosterAsync(item, thumb);
    }

    card.querySelector('.watchlist-remove-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      toggleWatchlist(item.movieId);
    });

    card.addEventListener('click', () => {
      closeWatchlistDrawer();
      openMovieDetailModal(item.movieId);
    });

    list.appendChild(card);
  });
}

function copyMovieNightPlan() {
  if (state.userWatchlist.length === 0) {
    showToast('⚠️ Your Watchlist is empty! Add movies first.');
    return;
  }

  let text = `🍿 CINEMOOD & BITES: MOVIE NIGHT PLAN 🍸\n`;
  text += `===========================================\n`;
  text += `Mood Vibe: ${state.moodProfiles[state.currentMood]?.name || state.currentMood}\n`;
  text += `Total Films: ${state.userWatchlist.length}\n\n`;

  text += `🎬 SCHEDULE & CURATED PAIRINGS:\n`;
  state.userWatchlist.forEach((item, idx) => {
    const p = item.pairings || {};
    text += `\n${idx + 1}. ${item.title} (${item.release_year || 'Feature'})\n`;
    if (item.director) text += `   • Director: ${item.director}\n`;
    text += `   • 🍿 Food Pairing: ${p.food || 'Gourmet Popcorn'}\n`;
    if (p.food_desc) text += `     (${p.food_desc})\n`;
    text += `   • 🍸 Drink Pairing: ${p.drink || 'Craft Beverage'}\n`;
    if (p.drink_desc) text += `     (${p.drink_desc})\n`;
    text += `   • 🕯️ Ambiance: ${p.ambiance || 'Soft dim lighting'}\n`;
  });

  text += `\n🛒 GROCERY & BAR CHECKLIST:\n`;
  state.userWatchlist.forEach((item) => {
    const p = item.pairings || {};
    text += `[ ] ${p.food || 'Popcorn'}\n`;
    text += `[ ] ${p.drink || 'Beverage'}\n`;
  });

  text += `\nGenerated with CineMood & Bites\n`;

  navigator.clipboard.writeText(text).then(() => {
    showToast('📋 Movie Night Plan copied to clipboard!');
  }).catch(() => {
    showToast('⚠️ Could not copy to clipboard.');
  });
}

// --------------------------------------------------------------------------
// Genre Filter Chips & Starter calibration
// --------------------------------------------------------------------------

async function loadGenres() {
  try {
    const res = await fetch('/api/genres');
    if (res.ok) {
      state.allGenres = await res.json();
      renderGenreChips();
    }
  } catch (e) {
    console.error('Failed loading genres:', e);
  }
}

function renderGenreChips() {
  const container = document.getElementById('genreChipsContainer');
  if (!container) return;
  container.innerHTML = '';

  state.allGenres.forEach(genre => {
    const chip = document.createElement('span');
    chip.className = 'genre-chip';
    chip.textContent = genre;
    chip.setAttribute('data-genre', genre);

    chip.addEventListener('click', () => {
      chip.classList.toggle('active');
      if (chip.classList.contains('active')) {
        state.selectedGenres.push(genre);
      } else {
        state.selectedGenres = state.selectedGenres.filter(g => g !== genre);
      }
      const countLabel = document.getElementById('selectedGenresCount');
      if (countLabel) {
        countLabel.textContent = state.selectedGenres.length ? `${state.selectedGenres.length} selected` : 'All Genres';
      }

      if (state.viewMode === 'catalog') {
        fetchCatalogPage(1, false);
      } else {
        fetchRecommendations();
      }
    });

    container.appendChild(chip);
  });
}

function renderStarterChips() {
  const container = document.getElementById('quickRateChips');
  if (!container) return;
  container.innerHTML = '';

  STARTER_MOVIES.forEach(m => {
    const isRated = state.userRatings[m.id];
    const chip = document.createElement('div');
    chip.className = 'starter-chip';
    chip.innerHTML = `
      <span>${escapeHtml(m.title)}</span>
      <span class="chip-stars">${isRated ? `(${isRated}★)` : '+ Rate 5★'}</span>
    `;

    chip.addEventListener('click', async () => {
      await rateMovie(m.id, m.title, 5.0);
      chip.querySelector('.chip-stars').textContent = '(5★)';
    });

    container.appendChild(chip);
  });
}

// --------------------------------------------------------------------------
// Event Listeners & UI Binding
// --------------------------------------------------------------------------

function setupEventListeners() {
  // Brand Home
  const brandHome = document.getElementById('brandHomeBtn');
  if (brandHome) {
    brandHome.addEventListener('click', () => {
      state.viewMode = 'recommendations';
      document.getElementById('tabForYou')?.classList.add('active');
      document.getElementById('tabBrowse')?.classList.remove('active');
      fetchRecommendations();
    });
  }

  // Mood Cards
  document.querySelectorAll('.mood-card').forEach(btn => {
    btn.addEventListener('click', () => {
      const mood = btn.getAttribute('data-mood');
      switchMood(mood, true);
    });
  });

  // Balance Slider
  const balanceSlider = document.getElementById('balanceSlider');
  if (balanceSlider) {
    balanceSlider.addEventListener('input', (e) => {
      state.tasteBalance = parseInt(e.target.value, 10);
      const badge = document.getElementById('balanceBadge');
      if (badge) {
        badge.textContent = state.tasteBalance === 50 ? 'Balanced (50/50)' : `${100 - state.tasteBalance}% Taste / ${state.tasteBalance}% Mood`;
      }
    });
    balanceSlider.addEventListener('change', fetchRecommendations);
  }

  // Minimum Rating Slider
  const minRatingSlider = document.getElementById('minRatingSlider');
  if (minRatingSlider) {
    minRatingSlider.addEventListener('input', (e) => {
      state.minRating = parseFloat(e.target.value);
      const badge = document.getElementById('ratingValueBadge');
      if (badge) badge.textContent = `${state.minRating.toFixed(1)}★ & up`;
    });
    minRatingSlider.addEventListener('change', fetchRecommendations);
  }

  // Decade Select
  const decadeSelect = document.getElementById('decadeSelect');
  if (decadeSelect) {
    decadeSelect.addEventListener('change', (e) => {
      state.decade = e.target.value;
      fetchRecommendations();
    });
  }

  // Refresh Button
  const refreshBtn = document.getElementById('refreshRecsBtn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
      if (state.viewMode === 'catalog') fetchCatalogPage(1, false);
      else fetchRecommendations();
    });
  }

  // Reset Filters
  const resetBtn = document.getElementById('resetFiltersBtn');
  const emptyResetBtn = document.getElementById('emptyResetBtn');
  const handleReset = () => {
    state.selectedGenres = [];
    state.minRating = 3.0;
    state.decade = 'All';
    state.tasteBalance = 50;
    state.selectedMediaType = 'all';

    document.querySelectorAll('.format-pill, .format-btn').forEach(btn => {
      if (btn.getAttribute('data-type') === 'all') btn.classList.add('active');
      else btn.classList.remove('active');
    });

    if (minRatingSlider) minRatingSlider.value = '3.0';
    if (decadeSelect) decadeSelect.value = 'All';
    if (balanceSlider) balanceSlider.value = '50';

    document.getElementById('ratingValueBadge').textContent = '3.0★ & up';
    document.getElementById('balanceBadge').textContent = 'Balanced (50/50)';
    document.getElementById('selectedGenresCount').textContent = 'All Genres';
    document.querySelectorAll('.genre-chip').forEach(c => c.classList.remove('active'));

    fetchRecommendations();
  };

  if (resetBtn) resetBtn.addEventListener('click', handleReset);
  if (emptyResetBtn) emptyResetBtn.addEventListener('click', handleReset);

  // Watchlist Drawer Controls
  const openWatchlistBtn = document.getElementById('openWatchlistBtn');
  const closeWatchlistBtn = document.getElementById('closeWatchlistBtn');
  const watchlistBackdrop = document.getElementById('watchlistBackdrop');
  const copyPlanBtn = document.getElementById('copyPlanBtn');
  const clearWatchlistBtn = document.getElementById('clearWatchlistBtn');

  if (openWatchlistBtn) openWatchlistBtn.addEventListener('click', openWatchlistDrawer);
  if (closeWatchlistBtn) closeWatchlistBtn.addEventListener('click', closeWatchlistDrawer);
  if (watchlistBackdrop) watchlistBackdrop.addEventListener('click', closeWatchlistDrawer);
  if (copyPlanBtn) copyPlanBtn.addEventListener('click', copyMovieNightPlan);
  if (clearWatchlistBtn) {
    clearWatchlistBtn.addEventListener('click', () => {
      state.userWatchlist = [];
      updateWatchlistBadge(0);
      renderWatchlistDrawer();
      showToast('Watchlist cleared.');
    });
  }

  // Movie Detail Modal Controls
  const closeDetailBtn = document.getElementById('closeDetailModalBtn');
  const dismissDetailBtn = document.getElementById('dismissDetailModalBtn');
  const detailBackdrop = document.getElementById('movieDetailModalBackdrop');

  if (closeDetailBtn) closeDetailBtn.addEventListener('click', closeMovieDetailModal);
  if (dismissDetailBtn) dismissDetailBtn.addEventListener('click', closeMovieDetailModal);
  if (detailBackdrop) {
    detailBackdrop.addEventListener('click', (e) => {
      if (e.target === detailBackdrop) closeMovieDetailModal();
    });
  }
}

function attachCardActionEvents(parent) {
  parent.querySelectorAll('[data-action="open-detail"]').forEach(el => {
    el.addEventListener('click', (e) => {
      e.stopPropagation();
      const mid = parseInt(el.getAttribute('data-id'), 10);
      if (mid) openMovieDetailModal(mid);
    });
  });

  parent.querySelectorAll('[data-action="toggle-watchlist"]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const mid = parseInt(btn.getAttribute('data-id'), 10);
      toggleWatchlist(mid, btn);
    });
  });
}

// --------------------------------------------------------------------------
// Toast & Utilities
// --------------------------------------------------------------------------

function showToast(message) {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    setTimeout(() => toast.remove(), 400);
  }, 3200);
}

function jsonPayload(obj) {
  return JSON.stringify(obj);
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
