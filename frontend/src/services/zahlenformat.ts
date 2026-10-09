export const euro = (wert: number | string) => `${Number(wert).toFixed(2).replace('.', ',')} €`;
