import type { Config } from 'tailwindcss';
export default { content: ['./app/**/*.{ts,tsx}','./components/**/*.{ts,tsx}','./observatory/**/*.{ts,tsx}','./candidate-lab/**/*.{ts,tsx}','./evidence-audit/**/*.{ts,tsx}'], theme: { extend: { colors: { void:'#070b14', panel:'#0d1524', ink:'#e7eefb', mute:'#91a0b8', cyan:'#83d6d2', amber:'#f2c977', rose:'#e8899b' } } }, plugins: [] } satisfies Config;
