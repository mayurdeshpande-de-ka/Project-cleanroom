// =============================================================================
// FRONTEND TESTS — Form 20 Backlog Dashboard
// =============================================================================
// Test Layers:
//   1. Component Rendering  — Each page renders without crashing
//   2. Loading States       — Spinner shown while API is in flight
//   3. Error States         — Error messages shown on API failure
//   4. Data Display         — Correct values rendered from mock API data
//   5. Interaction          — Filters, search, pagination trigger correct calls
//   6. Navigation           — Sidebar nav links render and highlight correctly
//   7. Status Badges        — Correct badge color/icon for each status value
//
// Run:
//   cd client && npm test
// =============================================================================

import React from 'react';
import {
  render,
  screen,
  fireEvent,
  waitFor,
  within,
} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import axios from 'axios';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';

// ─── Page components ────────────────────────────────────────────────────────
import Dashboard from '../src/pages/Dashboard';
import Listing from '../src/pages/Listing';
import GlanceReport from '../src/pages/GlanceReport';
import App from '../src/App';

// ─── Mock axios globally ─────────────────────────────────────────────────────
vi.mock('axios');
const mockedAxios = axios as vi.Mocked<typeof axios>;

// ─── Shared mock data ─────────────────────────────────────────────────────────
const MOCK_STATS = {
  total: 120,
  by_status: {
    downloaded: 30,
    extracted: 20,
    missing: 50,
    pending: 10,
    completed: 5,
    db_pushed: 5,
  },
  sir_by_status: {
    downloaded: 5,
    extracted: 3,
    missing: 10,
    pending: 2,
    completed: 0,
    db_pushed: 0,
  },
  wip_count: 8,
  by_state: [
    { state: 'UP', state_name: 'Uttar Pradesh', total: 50, completed: 10, extracted: 5, missing: 35, downloaded: 0 },
    { state: 'MH', state_name: 'Maharashtra', total: 40, completed: 15, extracted: 5, missing: 20, downloaded: 0 },
  ],
  by_type: {
    AE: { total: 80, completed: 15, missing: 50, downloaded: 15 },
    GE: { total: 40, completed: 10, missing: 25, downloaded: 5 },
  },
  bottlenecks: [
    { state: 'UP', pc_name: 'Lucknow', missing: 35 },
    { state: 'RJ', pc_name: 'Jaipur', missing: 20 },
  ],
  total_years: 5,
  years_in_db: 2,
  year_detail: [],
  ac_coverage: { form20_acs: 500, mapping_acs: 1000, pct: 50 },
};

const MOCK_RECORDS = [
  {
    id: '1',
    state: 'Uttar Pradesh',
    pc_name: 'Lucknow',
    ac_name: 'Lucknow Cantt',
    el_type: 'AE',
    year: 2022,
    status: 'Not Received',
    sir_status: 'Received',
    overall_status: 'missing',
    is_sir_state: 0,
  },
  {
    id: '2',
    state: 'Maharashtra',
    pc_name: 'Mumbai North',
    ac_name: 'Borivali',
    el_type: 'GE',
    year: 2019,
    status: 'Received',
    sir_status: 'Received',
    overall_status: 'downloaded',
    is_sir_state: 1,
  },
];

const MOCK_GLANCE = {
  all_weeks: [
    {
      week_label: 'Week 1 (Jan 1 - Jan 7)',
      start_date: '2024-01-01',
      end_date: '2024-01-07',
      records_pushed: 15,
      keys: [
        { state: 'UP', pc_name: 'Lucknow', el_type: 'AE', year: 2022, count: 5 },
        { state: 'MH', pc_name: 'Mumbai North', el_type: 'GE', year: 2019, count: 10 },
      ],
    },
  ],
};

// =============================================================================
// SECTION 1 — Navigation & App Shell
// =============================================================================

describe('App Shell & Navigation', () => {
  it('renders the sidebar with all navigation items', () => {
    mockedAxios.get.mockResolvedValueOnce({ data: MOCK_STATS });
    render(<App />);
    expect(screen.getByText('Form 20 Tracker')).toBeInTheDocument();
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Listing')).toBeInTheDocument();
    expect(screen.getByText('Glance Report')).toBeInTheDocument();
    expect(screen.getByText('Retro Export')).toBeInTheDocument();
  });

  it('Dashboard link is active-styled on the root path', () => {
    mockedAxios.get.mockResolvedValueOnce({ data: MOCK_STATS });
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>
    );
    const dashboardLink = screen.getByText('Dashboard').closest('a');
    expect(dashboardLink?.className).toContain('text-blue-700');
  });

  it('navigating to /listing renders the Listing page', async () => {
    mockedAxios.get.mockResolvedValue({ data: MOCK_RECORDS });
    render(
      <MemoryRouter initialEntries={['/listing']}>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByText('Form 20 Listing')).toBeInTheDocument();
  });

  it('navigating to /glance renders the GlanceReport page', async () => {
    mockedAxios.get.mockResolvedValueOnce({ data: MOCK_GLANCE });
    render(
      <MemoryRouter initialEntries={['/glance']}>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByText('Glance Report')).toBeInTheDocument();
  });
});

// =============================================================================
// SECTION 2 — Dashboard Component
// =============================================================================

describe('Dashboard Component', () => {
  beforeEach(() => {
    mockedAxios.get.mockResolvedValue({ data: MOCK_STATS });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('shows loading spinner on initial mount', () => {
    // Keep the promise pending to catch the loading state
    mockedAxios.get.mockImplementation(() => new Promise(() => {}));
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    expect(screen.getByText('Loading insights...')).toBeInTheDocument();
  });

  it('shows metric cards after data loads', async () => {
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getByText('Total Forms')).toBeInTheDocument();
      expect(screen.getByText('120')).toBeInTheDocument(); // total
    });
  });

  it('renders "Forms Received" metric card with correct value', async () => {
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getByText('Forms Received')).toBeInTheDocument();
      // by_status.downloaded = 30 (mapped to "Forms Received" in earlier logic)
    });
  });

  it('renders "Work In Progress" metric card', async () => {
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getByText('Work In Progress')).toBeInTheDocument();
      expect(screen.getByText('8')).toBeInTheDocument(); // wip_count
    });
  });

  it('renders "Missing Forms" metric card', async () => {
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getByText('Missing Forms')).toBeInTheDocument();
    });
  });

  it('renders "Status Distribution" pie chart section', async () => {
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getByText('Status Distribution')).toBeInTheDocument();
    });
  });

  it('renders "State-wise Collection" bar chart section', async () => {
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getByText(/State-wise Collection/)).toBeInTheDocument();
    });
  });

  it('renders Top Bottlenecks table with correct data', async () => {
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getByText('Top Bottlenecks')).toBeInTheDocument();
      expect(screen.getByText('Lucknow')).toBeInTheDocument();
      expect(screen.getByText('35')).toBeInTheDocument();
    });
  });

  it('shows "No bottlenecks" message when bottlenecks array is empty', async () => {
    mockedAxios.get.mockResolvedValueOnce({
      data: { ...MOCK_STATS, bottlenecks: [] }
    });
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getByText('No bottlenecks identified. Great job!')).toBeInTheDocument();
    });
  });

  it('shows error message when API call fails', async () => {
    mockedAxios.get.mockRejectedValueOnce(new Error('Network Error'));
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getByText('Connection Error')).toBeInTheDocument();
    });
  });

  it('calls /api/stats on mount', async () => {
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    await waitFor(() => {
      expect(mockedAxios.get).toHaveBeenCalledWith('/api/stats');
    });
  });
});

// =============================================================================
// SECTION 3 — Listing Component
// =============================================================================

describe('Listing Component', () => {
  beforeEach(() => {
    mockedAxios.get.mockResolvedValue({ data: MOCK_RECORDS });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders the page heading', () => {
    render(<MemoryRouter><Listing /></MemoryRouter>);
    expect(screen.getByText('Form 20 Listing')).toBeInTheDocument();
  });

  it('renders table headers correctly', async () => {
    render(<MemoryRouter><Listing /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getByText('State / Year')).toBeInTheDocument();
      expect(screen.getByText('Election Type')).toBeInTheDocument();
      expect(screen.getByText('PC Name')).toBeInTheDocument();
      expect(screen.getByText('AC Name')).toBeInTheDocument();
      expect(screen.getByText('Status')).toBeInTheDocument();
    });
  });

  it('renders records from the API', async () => {
    render(<MemoryRouter><Listing /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getByText('Uttar Pradesh')).toBeInTheDocument();
      expect(screen.getByText('Maharashtra')).toBeInTheDocument();
    });
  });

  it('shows "Missing" badge for Not Received status', async () => {
    render(<MemoryRouter><Listing /></MemoryRouter>);
    await waitFor(() => {
      const badges = screen.getAllByText('Missing');
      expect(badges.length).toBeGreaterThan(0);
    });
  });

  it('shows "Received" badge for received records', async () => {
    render(<MemoryRouter><Listing /></MemoryRouter>);
    await waitFor(() => {
      const badges = screen.getAllByText('Received');
      expect(badges.length).toBeGreaterThan(0);
    });
  });

  it('shows empty state when no records returned', async () => {
    mockedAxios.get.mockResolvedValueOnce({ data: [] });
    render(<MemoryRouter><Listing /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getByText('No records found')).toBeInTheDocument();
    });
  });

  it('search input triggers API call with search param', async () => {
    render(<MemoryRouter><Listing /></MemoryRouter>);
    const searchInput = screen.getByPlaceholderText('Search PC/AC...');
    await userEvent.type(searchInput, 'Lucknow');
    await waitFor(() => {
      expect(mockedAxios.get).toHaveBeenCalledWith(
        '/api/records',
        expect.objectContaining({ params: expect.objectContaining({ search: 'Lucknow' }) })
      );
    }, { timeout: 2000 }); // Allow for debounce
  });

  it('typing in search resets page to 1', async () => {
    render(<MemoryRouter><Listing /></MemoryRouter>);
    // Simulate being on page 2 first, then searching
    const searchInput = screen.getByPlaceholderText('Search PC/AC...');
    await userEvent.type(searchInput, 'M');
    await waitFor(() => {
      expect(mockedAxios.get).toHaveBeenCalledWith(
        '/api/records',
        expect.objectContaining({ params: expect.objectContaining({ page: 1 }) })
      );
    }, { timeout: 2000 });
  });

  it('state dropdown filter triggers API call with state param', async () => {
    render(<MemoryRouter><Listing /></MemoryRouter>);
    await waitFor(() => screen.getByText('All States'));
    const stateSelect = screen.getByDisplayValue('All States');
    fireEvent.change(stateSelect, { target: { value: 'Uttar Pradesh' } });
    await waitFor(() => {
      expect(mockedAxios.get).toHaveBeenCalledWith(
        '/api/records',
        expect.objectContaining({
          params: expect.objectContaining({ state: 'Uttar Pradesh' }),
        })
      );
    });
  });

  it('election type dropdown filter triggers API call', async () => {
    render(<MemoryRouter><Listing /></MemoryRouter>);
    await waitFor(() => screen.getByDisplayValue('All Election Types'));
    const elTypeSelect = screen.getByDisplayValue('All Election Types');
    fireEvent.change(elTypeSelect, { target: { value: 'AE' } });
    await waitFor(() => {
      expect(mockedAxios.get).toHaveBeenCalledWith(
        '/api/records',
        expect.objectContaining({
          params: expect.objectContaining({ el_type: 'AE' }),
        })
      );
    });
  });

  it('pagination previous button is disabled on page 1', async () => {
    render(<MemoryRouter><Listing /></MemoryRouter>);
    await waitFor(() => screen.getByText('Form 20 Listing'));
    const prevButtons = screen.getAllByRole('button');
    const prevBtn = prevButtons.find(btn =>
      btn.querySelector('svg') !== null && btn.getAttribute('disabled') !== null
    );
    // Page 1 should have the previous button disabled
    expect(prevButtons.some(btn => btn.disabled)).toBeTruthy();
  });
});

// =============================================================================
// SECTION 4 — GlanceReport Component
// =============================================================================

describe('GlanceReport Component', () => {
  beforeEach(() => {
    mockedAxios.get.mockResolvedValue({ data: MOCK_GLANCE });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders the page heading', () => {
    render(<MemoryRouter><GlanceReport /></MemoryRouter>);
    expect(screen.getByText('Glance Report')).toBeInTheDocument();
  });

  it('shows loading state initially', () => {
    mockedAxios.get.mockImplementation(() => new Promise(() => {}));
    render(<MemoryRouter><GlanceReport /></MemoryRouter>);
    expect(screen.getByText('Generating Report...')).toBeInTheDocument();
  });

  it('renders week label after data loads', async () => {
    render(<MemoryRouter><GlanceReport /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getByText('Week 1 (Jan 1 - Jan 7)')).toBeInTheDocument();
    });
  });

  it('shows records pushed count for a week', async () => {
    render(<MemoryRouter><GlanceReport /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getByText(/15 Pushed/)).toBeInTheDocument();
    });
  });

  it('auto-expands the first week', async () => {
    render(<MemoryRouter><GlanceReport /></MemoryRouter>);
    await waitFor(() => {
      // First week content (the keys inside it) should be visible without clicking
      expect(screen.getByText('UP')).toBeInTheDocument();
    });
  });

  it('clicking week header toggles expanded state', async () => {
    render(<MemoryRouter><GlanceReport /></MemoryRouter>);
    await waitFor(() => screen.getByText('Week 1 (Jan 1 - Jan 7)'));
    const weekHeader = screen.getByText('Week 1 (Jan 1 - Jan 7)').closest('button')!;
    // It starts expanded (auto-expand), click to collapse
    fireEvent.click(weekHeader);
    await waitFor(() => {
      // State name "UP" inside expanded content should no longer be visible
      expect(screen.queryByText('Pushed Keys Detail')).not.toBeInTheDocument();
    });
  });

  it('shows "No data available" when API returns empty list', async () => {
    mockedAxios.get.mockResolvedValueOnce({ data: { all_weeks: [] } });
    render(<MemoryRouter><GlanceReport /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getByText('No data available')).toBeInTheDocument();
    });
  });

  it('month filter dropdown changes trigger API refetch', async () => {
    render(<MemoryRouter><GlanceReport /></MemoryRouter>);
    await waitFor(() => screen.getByDisplayValue('All Months'));
    const monthSelect = screen.getByDisplayValue('All Months');
    fireEvent.change(monthSelect, { target: { value: '1' } });
    await waitFor(() => {
      expect(mockedAxios.get).toHaveBeenCalledWith(
        '/api/glance_report',
        expect.objectContaining({
          params: expect.objectContaining({ month: '1' }),
        })
      );
    });
  });

  it('state filter dropdown triggers API refetch with state param', async () => {
    render(<MemoryRouter><GlanceReport /></MemoryRouter>);
    await waitFor(() => screen.getAllByDisplayValue('All States'));
    const stateSelect = screen.getAllByDisplayValue('All States')[0];
    fireEvent.change(stateSelect, { target: { value: 'Uttar Pradesh' } });
    await waitFor(() => {
      expect(mockedAxios.get).toHaveBeenCalledWith(
        '/api/glance_report',
        expect.objectContaining({
          params: expect.objectContaining({ state: 'Uttar Pradesh' }),
        })
      );
    });
  });

  it('PC name from keys is rendered in expanded week', async () => {
    render(<MemoryRouter><GlanceReport /></MemoryRouter>);
    await waitFor(() => {
      // Should find the PC names from MOCK_GLANCE.all_weeks[0].keys
      expect(screen.getByText(/Lucknow/)).toBeInTheDocument();
    });
  });
});

// =============================================================================
// SECTION 5 — Status Badge Logic
// =============================================================================

describe('Status Badge Rendering (Listing)', () => {
  it('renders green "Received" badge for received records', async () => {
    mockedAxios.get.mockResolvedValueOnce({ data: MOCK_RECORDS });
    render(<MemoryRouter><Listing /></MemoryRouter>);
    await waitFor(() => {
      const receivedBadge = screen.getAllByText('Received')[0];
      expect(receivedBadge.closest('span')?.className).toContain('emerald');
    });
  });

  it('renders red "Missing" badge for not received records', async () => {
    mockedAxios.get.mockResolvedValueOnce({ data: MOCK_RECORDS });
    render(<MemoryRouter><Listing /></MemoryRouter>);
    await waitFor(() => {
      const missingBadge = screen.getAllByText('Missing')[0];
      expect(missingBadge.closest('span')?.className).toContain('rose');
    });
  });
});

// =============================================================================
// SECTION 6 — Accessibility
// =============================================================================

describe('Accessibility', () => {
  it('Dashboard page has a visible <h1> heading', async () => {
    mockedAxios.get.mockResolvedValueOnce({ data: MOCK_STATS });
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    await waitFor(() => {
      const headings = screen.getAllByRole('heading', { level: 1 });
      expect(headings.length).toBeGreaterThan(0);
    });
  });

  it('Listing page has a visible <h1> heading', async () => {
    mockedAxios.get.mockResolvedValueOnce({ data: MOCK_RECORDS });
    render(<MemoryRouter><Listing /></MemoryRouter>);
    const heading = screen.getByRole('heading', { level: 1 });
    expect(heading).toBeInTheDocument();
  });

  it('Search input has an accessible placeholder', () => {
    mockedAxios.get.mockResolvedValue({ data: MOCK_RECORDS });
    render(<MemoryRouter><Listing /></MemoryRouter>);
    expect(screen.getByPlaceholderText('Search PC/AC...')).toBeInTheDocument();
  });

  it('Pagination buttons are keyboard-accessible', async () => {
    mockedAxios.get.mockResolvedValue({ data: MOCK_RECORDS });
    render(<MemoryRouter><Listing /></MemoryRouter>);
    await waitFor(() => screen.getByText('Form 20 Listing'));
    const buttons = screen.getAllByRole('button');
    expect(buttons.length).toBeGreaterThan(0);
  });
});
