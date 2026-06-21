import { TViewData } from 'equicharts';

import {
  Datafeed,
  SymbolInfo,
  Period,
  DatafeedSubscribeCallback,
} from './types';
import { data } from './data';

const API_BASE = import.meta.env.VITE_API_URL || '/api/v1';
console.log(API_BASE)
export class MainDatafeed implements Datafeed {
  private apiBase: string;
  private subscriptions: Map<string, { callback: DatafeedSubscribeCallback, interval?: NodeJS.Timeout }>;

  constructor(apiBase: string = API_BASE) {
    this.apiBase = apiBase;
    this.subscriptions = new Map();
  }

  /**
   * Search for symbols (uses your backend's search or fallback)
   */
  async searchSymbols(search?: string): Promise<SymbolInfo[]> {
    if (!search || search.length < 1) {
      return [];
    }

    try {
      const response = await fetch(
        `${this.apiBase}/search?q=${encodeURIComponent(search)}`
      );
      
      if (!response.ok) {
        throw new Error(`Search failed: ${response.statusText}`);
      }
      
      const data = await response.json();
      
      // Handle both response formats
      const results = data.results || data;
      
      return results.map((item: any) => ({
        ticker: item.symbol || item.ticker,
        name: item.name,
        exchange: item.exchange,
        market: item.market || 'US',
        type: item.type || 'Equity',
        priceCurrency: item.currency || 'USD',
      }));
      
    } catch (error) {
      console.error('Symbol search failed:', error);
      return this.getFallbackSymbols(search);
    }
  }

  /**
   * Fetch historical data from your backend
   * This is the main data ingestion method that matches your Python API
   */
  async getHistoryTViewData(
    symbol: SymbolInfo,
    period: Period,
    from: number,
    to: number,
  ): Promise<TViewData[]> {
    try {
      // Map EquiCharts Period to your backend's interval/period
      const { interval, periodRange } = this.mapPeriodToBackend(period, from, to);
      
      // Build URL to your backend
      const url = new URL(`${this.apiBase}/stock/${symbol.ticker}`);
      url.searchParams.append('interval', interval);
      url.searchParams.append('period', periodRange);
      
      console.log(`📊 Fetching ${symbol.ticker} from backend:`, url.toString());
      
      const response = await fetch(url.toString());
      
      if (!response.ok) {
        throw new Error(`Backend error: ${response.status} ${response.statusText}`);
      }
      
      const data = await response.json();
      
      // Handle both response formats (wrapped or direct array)
      const bars = data.data || data;
      
      if (!Array.isArray(bars) || bars.length === 0) {
        console.warn(`No data returned for ${symbol.ticker}`);
        return [];
      }
      
      // Transform to TViewData format (EquiCharts expects)
      return bars
        .filter((point: any) => point.time >= from && point.time <= to)
        .map((point: any) => ({
          time: point.time,
          open: point.open,
          high: point.high,
          low: point.low,
          close: point.close,
          volume: point.volume,
          change: 0,  // Optional: calculate if needed
          turnover: 0, // Optional: calculate if needed
        }));
      
    } catch (error) {
      console.error(`Error fetching data for ${symbol.ticker}:`, error);
      return [];
    }
  }

  /**
   * Subscribe to real-time updates (using your backend's WebSocket or polling)
   */
  subscribe(
    symbol: SymbolInfo,
    period: Period,
    callback: DatafeedSubscribeCallback,
  ): void {
    const key = `${symbol.ticker}_${period.multiplier}_${period.timespan}`;
    
    // Prevent duplicate subscriptions
    if (this.subscriptions.has(key)) {
      console.warn(`Already subscribed to ${symbol.ticker}`);
      return;
    }
    
    console.log(`📡 Subscribing to ${symbol.ticker} updates (polling)`);
    
    // Poll your backend every 30 seconds for updates
    const interval = setInterval(async () => {
      try {
        // Get the latest bar (1 day of data)
        const url = new URL(`${this.apiBase}/stock/${symbol.ticker}`);
        url.searchParams.append('interval', '1d');
        url.searchParams.append('period', '1d');
        
        const response = await fetch(url.toString());
        if (!response.ok) return;
        
        const data = await response.json();
        const bars = data.data || data;
        
        if (bars && bars.length > 0) {
          const latest = bars[bars.length - 1];
          callback({
            time: latest.time,
            open: latest.open,
            high: latest.high,
            low: latest.low,
            close: latest.close,
            volume: latest.volume,
            change: 0,
            turnover: 0,
          });
        }
      } catch (error) {
        console.error('Subscription poll error:', error);
      }
    }, 30000); // 30 seconds
    
    this.subscriptions.set(key, { callback, interval });
  }

  /**
   * Unsubscribe from real-time updates
   */
  unsubscribe(symbol: SymbolInfo, period: Period): void {
    const key = `${symbol.ticker}_${period.multiplier}_${period.timespan}`;
    const subscription = this.subscriptions.get(key);
    
    if (subscription?.interval) {
      clearInterval(subscription.interval);
      this.subscriptions.delete(key);
      console.log(`📡 Unsubscribed from ${symbol.ticker}`);
    }
  }

  /**
   * Map EquiCharts Period to your backend's parameters
   */
  private mapPeriodToBackend(period: Period, from: number, to: number): { interval: string; periodRange: string } {
    // Map timespan to interval
    const intervalMap: Record<string, Record<number, string>> = {
      'minute': { 1: '1m', 5: '5m', 15: '15m', 30: '30m' },
      'hour': { 1: '1h', 2: '2h', 4: '4h' },
      'day': { 1: '1d' },
      'week': { 1: '1wk' },
      'month': { 1: '1mo' },
      'year': { 1: '1y' },
    };
    
    const interval = intervalMap[period.timespan]?.[period.multiplier] || '1d';
    
    // Calculate period range from from/to timestamps
    const diffMs = to - from;
    const diffDays = diffMs / (1000 * 60 * 60 * 24);
    
    let periodRange: string;
    if (diffDays <= 1) periodRange = '1d';
    else if (diffDays <= 5) periodRange = '5d';
    else if (diffDays <= 30) periodRange = '1mo';
    else if (diffDays <= 90) periodRange = '3mo';
    else if (diffDays <= 180) periodRange = '6mo';
    else if (diffDays <= 365) periodRange = '1y';
    else if (diffDays <= 730) periodRange = '2y';
    else if (diffDays <= 1825) periodRange = '5y';
    else periodRange = 'max';
    
    return { interval, periodRange };
  }

  /**
   * Fallback symbols for when search fails
   */
  private getFallbackSymbols(search: string): SymbolInfo[] {
    const symbols = [
      { ticker: 'AAPL', name: 'Apple Inc.', exchange: 'NASDAQ' },
      { ticker: 'MSFT', name: 'Microsoft Corp.', exchange: 'NASDAQ' },
      { ticker: 'GOOGL', name: 'Alphabet Inc.', exchange: 'NASDAQ' },
      { ticker: 'AMZN', name: 'Amazon.com Inc.', exchange: 'NASDAQ' },
      { ticker: 'TSLA', name: 'Tesla Inc.', exchange: 'NASDAQ' },
      { ticker: 'NVDA', name: 'NVIDIA Corp.', exchange: 'NASDAQ' },
      { ticker: '00700.HK', name: 'Tencent Holdings', exchange: 'HKEX' },
      { ticker: '09988.HK', name: 'Alibaba Group', exchange: 'HKEX' },
      { ticker: '00005.HK', name: 'HSBC Holdings', exchange: 'HKEX' },
    ];
    
    const searchLower = search.toLowerCase();
    return symbols.filter(s =>
      s.ticker.toLowerCase().includes(searchLower) ||
      s.name.toLowerCase().includes(searchLower)
    );
  }
}

// Singleton instance
export const mainDatafeed = new MainDatafeed();