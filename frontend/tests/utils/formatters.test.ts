import { describe, it, expect } from 'vitest';
import {
  formatPercent,
  formatNumber,
  formatCI,
  formatRial,
  formatDay,
} from '../../src/utils/formatters';

describe('formatters', () => {
  describe('formatPercent', () => {
    it('formats probability as percentage', () => {
      expect(formatPercent(0.8302)).toBe('83.0%');
      expect(formatPercent(0.054)).toBe('5.4%');
    });

    it('respects decimal places parameter', () => {
      expect(formatPercent(0.8302, 0)).toBe('83%');
      expect(formatPercent(0.8302, 2)).toBe('83.02%');
    });

    it('handles edge cases', () => {
      expect(formatPercent(0)).toBe('0.0%');
      expect(formatPercent(1)).toBe('100.0%');
    });
  });

  describe('formatNumber', () => {
    it('formats large numbers with commas', () => {
      expect(formatNumber(1429000)).toBe('1,429,000');
      expect(formatNumber(10000)).toBe('10,000');
    });

    it('handles small numbers', () => {
      expect(formatNumber(999)).toBe('999');
      expect(formatNumber(0)).toBe('0');
    });
  });

  describe('formatCI', () => {
    it('formats confidence intervals', () => {
      expect(formatCI(0.82, 0.84)).toBe('82% - 84%');
      expect(formatCI(0.05, 0.06)).toBe('5% - 6%');
    });
  });

  describe('formatRial', () => {
    it('formats rial currency', () => {
      expect(formatRial(1429000)).toBe('1,429,000 IRR');
    });
  });

  describe('formatDay', () => {
    it('formats day numbers', () => {
      expect(formatDay(0)).toBe('Day 0');
      expect(formatDay(45)).toBe('Day 45');
      expect(formatDay(90)).toBe('Day 90');
    });
  });
});
