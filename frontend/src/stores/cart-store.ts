import { create } from "zustand";
import { persist } from "zustand/middleware";

/**
 * Client-side cart store (starter).
 *
 * This is the client mirror of the cart for instant UI feedback; the server
 * (Redis-backed cart on the backend) remains the source of truth at checkout.
 * Persisted to localStorage so the cart survives reloads. Expand item shape and
 * actions as the storefront is built (P3).
 */
export interface CartItem {
  productId: string;
  title: string;
  unitPrice: number;
  quantity: number;
}

interface CartState {
  items: CartItem[];
  addItem: (item: CartItem) => void;
  removeItem: (productId: string) => void;
  setQuantity: (productId: string, quantity: number) => void;
  clear: () => void;
  totalQuantity: () => number;
}

export const useCartStore = create<CartState>()(
  persist(
    (set, get) => ({
      items: [],
      addItem: (item) =>
        set((state) => {
          const existing = state.items.find(
            (i) => i.productId === item.productId,
          );
          if (existing) {
            return {
              items: state.items.map((i) =>
                i.productId === item.productId
                  ? { ...i, quantity: i.quantity + item.quantity }
                  : i,
              ),
            };
          }
          return { items: [...state.items, item] };
        }),
      removeItem: (productId) =>
        set((state) => ({
          items: state.items.filter((i) => i.productId !== productId),
        })),
      setQuantity: (productId, quantity) =>
        set((state) => ({
          items: state.items.flatMap((i) => {
            if (i.productId !== productId) return [i];
            return quantity > 0 ? [{ ...i, quantity }] : [];
          }),
        })),
      clear: () => set({ items: [] }),
      totalQuantity: () => get().items.reduce((sum, i) => sum + i.quantity, 0),
    }),
    { name: "shopflow-cart" },
  ),
);
