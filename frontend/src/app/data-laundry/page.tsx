// Data Laundry page - Separate route for data cleaning and labeling
// Version: 1.0 - Extracted from dashboard as standalone page for URL persistence

'use client';

import TabNavigation from '@/components/TabNavigation';
import DataCleaningTab from '@/components/DataCleaningTab';

export default function DataLaundryPage() {
  return (
    <div className="min-h-screen bg-stone-900">
      {/* Header */}
      <header className="bg-stone-800 border-b border-stone-700 py-6 px-8">
        <div className="max-w-[1400px] mx-auto">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h1 className="text-2xl font-semibold text-stone-50 tracking-tight">
                XHS Multi-Account Scraper
              </h1>
              <p className="text-sm text-stone-500 mt-1 font-mono">
                Manage accounts and scrape Xiaohongshu posts in parallel
              </p>
            </div>
            <TabNavigation />
          </div>
        </div>
      </header>

      <main className="max-w-[1400px] mx-auto px-8 py-8">
        <DataCleaningTab />
      </main>

      {/* Footer */}
      <footer className="mt-16 py-6 text-center text-stone-600 text-sm font-mono">
        <p>XHS Multi-Account Scraper</p>
      </footer>
    </div>
  );
}
