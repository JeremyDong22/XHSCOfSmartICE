// Tab Navigation component for switching between Dashboard and Data Laundry
// Version: 1.1 - Changed to use Next.js Link for proper routing with URL persistence
// Changes: Replaced buttons with Links, uses usePathname for active detection
// Previous: Used onClick handlers with state-based tab switching

'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

interface Tab {
  id: string;
  label: string;
  icon: React.ReactNode;
  href: string;
}

// Dashboard icon - grid layout
const DashboardIcon = () => (
  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="3" y="3" width="7" height="7" rx="1" />
    <rect x="14" y="3" width="7" height="7" rx="1" />
    <rect x="3" y="14" width="7" height="7" rx="1" />
    <rect x="14" y="14" width="7" height="7" rx="1" />
  </svg>
);

// Washing machine icon - funky data laundry symbol
const LaundryIcon = () => (
  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="2" y="2" width="20" height="20" rx="3" />
    <circle cx="12" cy="13" r="6" />
    <path d="M9 13c0-1.5 1.5-2 3-2s3 .5 3 2-1.5 2-3 2-3-.5-3-2" />
    <circle cx="6" cy="6" r="1" fill="currentColor" />
    <circle cx="10" cy="6" r="1" fill="currentColor" />
  </svg>
);

const tabs: Tab[] = [
  { id: 'dashboard', label: 'Dashboard', icon: <DashboardIcon />, href: '/' },
  { id: 'data-laundry', label: 'Data Laundry', icon: <LaundryIcon />, href: '/data-laundry' },
];

export default function TabNavigation() {
  const pathname = usePathname();

  const isActive = (href: string) => {
    if (href === '/') return pathname === '/';
    return pathname.startsWith(href);
  };

  return (
    <div className="flex items-center gap-1 bg-stone-900 rounded-lg p-1 border border-stone-700">
      {tabs.map((tab) => (
        <Link
          key={tab.id}
          href={tab.href}
          className={`flex items-center gap-2 px-4 py-2 rounded-md font-medium text-sm transition-all ${
            isActive(tab.href)
              ? 'bg-[rgba(217,119,87,0.2)] text-[#E8A090] border border-[rgba(217,119,87,0.3)]'
              : 'text-stone-400 hover:text-stone-200 hover:bg-stone-800 border border-transparent'
          }`}
        >
          {tab.icon}
          {tab.label}
        </Link>
      ))}
    </div>
  );
}
