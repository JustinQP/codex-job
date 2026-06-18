import { useEffect, useState } from "react";

import { readStorage, writeStorage } from "../state/storage";

export function useLocalStorage(key: string, initialValue: string) {
  const [value, setValue] = useState(() => readStorage(key, initialValue));

  useEffect(() => {
    writeStorage(key, value);
  }, [key, value]);

  return [value, setValue] as const;
}
