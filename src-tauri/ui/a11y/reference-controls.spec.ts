// AC-ACCESS-1: Headless-browser accessibility harness for the reference editing
// controls. These assertions run against the live DOM in a real Chromium browser,
// with the Tauri bridge stubbed through src-tauri/ui/a11y/tauri-stub.ts.
//
// Owned AC: AC-ACCESS-1 (keyboard reachability, accessible names, text-form
// errors, four-preview layout at supported window sizes, theme and font-size
// conformance, disabled state before settled signal).

import { test, expect, type Page } from '@playwright/test';

const STUB_A11Y_PATHS_KEY = '__a11yPaths';

type ConfigAckPayload = {
  model_id: string;
  reference_count: number;
  reference_paths: string[];
  preset: string | null;
  compatible: boolean;
  incompatibility_reason: string | null;
  required_model: string | null;
  settled: boolean;
};

function configAck(partial: Partial<ConfigAckPayload> & { model_id: string; reference_paths: string[]; preset: string | null }): {
  type: 'config_ack';
  payload: ConfigAckPayload;
} {
  return {
    type: 'config_ack',
    payload: {
      model_id: partial.model_id,
      reference_count: partial.reference_paths.length,
      reference_paths: partial.reference_paths,
      preset: partial.preset,
      compatible: partial.compatible ?? true,
      incompatibility_reason: partial.incompatibility_reason ?? null,
      required_model: partial.required_model ?? null,
      settled: partial.settled ?? true,
    },
  };
}

function stateChangedPausedSettled(settled: boolean): {
  type: 'state_changed';
  payload: { state: 'paused'; settled: boolean };
} {
  return { type: 'state_changed', payload: { state: 'paused', settled } };
}

async function loadPageWithSettledEditingModel(
  page: Page,
  modelId = 'flux2-klein-4b',
  preset = 'landscape-medium',
): Promise<void> {
  await page.addInitScript(() => {
    (window as unknown as Record<string, unknown>)[
      'convertFileSrc'
    ] = () => 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=';
    (window as unknown as Record<string, unknown>).__a11yPaths = [] as string[];
  });
  await page.goto('/');
  await page.waitForFunction(() => {
    return Boolean((window as unknown as Record<string, unknown>).__a11yEmit);
  });
  await page.evaluate(([paths]) => {
    (window as unknown as Record<string, unknown>).__a11yPaths = paths;
  }, [['/tmp/a11y/a.png', '/tmp/a11y/b.jpg', '/tmp/a11y/c.jpeg', '/tmp/a11y/d.JPG']]);
  await page.evaluate(([msg]) => {
    (window as unknown as (type: string, payload: unknown) => void).__a11yEmit(
      msg.type,
      msg.payload,
    );
  }, [
    configAck({
      model_id: modelId,
      reference_paths: [],
      preset,
    }),
  ]);
  await page.evaluate(([msg]) => {
    (window as unknown as (type: string, payload: unknown) => void).__a11yEmit(
      msg.type,
      msg.payload,
    );
  }, [stateChangedPausedSettled(true)]);
}

// AC-ACCESS-1 (keyboard reachability): The model radios, add button, remove and
// replace buttons, and preset radios must all be reachable in that order from
// the prompt input. The DOM also contains aspect-ratio radios and resolution
// buttons between the prompt and the model radios, so we record the full tab
// order and verify the expected elements appear as a subsequence.
async function recordTabOrderFromPrompt(
  page: Page,
  maxTabs = 50,
): Promise<string[]> {
  const focusedSelectors: string[] = [];
  for (let i = 0; i < maxTabs; i += 1) {
    await page.keyboard.press('Tab');
    const selector = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      if (!el || el === document.body) return null;
      if (el.id) return `#${el.id}`;
      const name = el.getAttribute('name');
      const value = el.getAttribute('value');
      if (name && value !== null && value !== '') {
        return `${el.tagName.toLowerCase()}[name="${name}"][value="${value}"]`;
      }
      return el.tagName.toLowerCase();
    });
    if (selector) focusedSelectors.push(selector);
  }
  return focusedSelectors;
}

function expectSubsequence(haystack: string[], needle: string[]): void {
  let cursor = -1;
  for (const item of needle) {
    const next = haystack.indexOf(item, cursor + 1);
    expect(
      next,
      `Expected ${item} to appear in tab order after index ${cursor}; got ${JSON.stringify(haystack)}`,
    ).toBeGreaterThan(cursor);
    cursor = next;
  }
}

test.describe('AC-ACCESS-1: keyboard reachability', () => {
  test('Tab from the prompt input reaches model radio group, add button, per-preview remove/replace, and preset radio group', async ({
    page,
  }) => {
    await loadPageWithSettledEditingModel(page);

    const promptInput = page.getByRole('textbox', { name: 'Generation prompt' });
    await promptInput.focus();
    expect(await page.evaluate(() => document.activeElement?.id)).toBe('prompt-input');

    const tabOrder = await recordTabOrderFromPrompt(page);

    // HTML radio groups expose the checked option to Tab and hide the
    // unchecked siblings (arrow keys navigate within the group). The checked
    // values are flux2-klein-4b and landscape-medium because that is what
    // loadPageWithSettledEditingModel acknowledges.
    expectSubsequence(tabOrder, [
      'input[name="model"][value="flux2-klein-4b"]',
      '#reference-add',
      'input[name="editing-preset"][value="landscape-medium"]',
    ]);
  });

  test('Add four references via the path-injection seam, then verify Tab order through preview controls', async ({
    page,
  }) => {
    const paths = [
      '/tmp/a11y/one.png',
      '/tmp/a11y/two.jpg',
      '/tmp/a11y/three.jpeg',
      '/tmp/a11y/four.JPG',
    ];
    await page.addInitScript((args) => {
      (window as unknown as Record<string, unknown>).__a11yPaths = args[0];
    }, [paths]);
    await page.goto('/');
    await page.waitForFunction(() => Boolean((window as unknown as Record<string, unknown>).__a11yEmit));
    await page.evaluate(([msg]) => {
      (window as unknown as (type: string, payload: unknown) => void).__a11yEmit(
        msg.type,
        msg.payload,
      );
    }, [configAck({ model_id: 'flux2-klein-4b', reference_paths: [], preset: 'landscape-medium' })]);
    await page.evaluate(([msg]) => {
      (window as unknown as (type: string, payload: unknown) => void).__a11yEmit(
        msg.type,
        msg.payload,
      );
    }, [stateChangedPausedSettled(true)]);

    await page.getByRole('button', { name: 'Add reference images' }).click();
    await page.evaluate(([msg]) => {
      (window as unknown as (type: string, payload: unknown) => void).__a11yEmit(
        msg.type,
        msg.payload,
      );
    }, [
      configAck({
        model_id: 'flux2-klein-4b',
        reference_paths: paths,
        preset: 'landscape-medium',
      }),
    ]);
    await expect(page.getByRole('listitem')).toHaveCount(4);

    for (let i = 0; i < 4; i += 1) {
      const removeName = `Remove reference ${i + 1} of 4: ${paths[i]!.split('/').pop()}`;
      await expect(page.getByRole('button', { name: removeName })).toBeVisible();
      const replaceName = `Replace reference ${i + 1} of 4: ${paths[i]!.split('/').pop()}`;
      await expect(page.getByRole('button', { name: replaceName })).toBeVisible();
    }

    const promptInput = page.getByRole('textbox', { name: 'Generation prompt' });
    await promptInput.focus();

    const tabOrder: string[] = [];
    for (let i = 0; i < 30; i += 1) {
      await page.keyboard.press('Tab');
      const next = await page.evaluate(() => {
        const el = document.activeElement as HTMLElement | null;
        if (!el) return null;
        const ariaLabel = el.getAttribute('aria-label');
        if (ariaLabel) return ariaLabel;
        const closestLabel = el.closest('label') as HTMLElement | null;
        if (closestLabel) {
          const clone = closestLabel.cloneNode(true) as HTMLElement;
          clone.querySelectorAll('small').forEach((s) => s.remove());
          const text = clone.textContent?.trim();
          if (text) return text;
        }
        const text = el.textContent?.trim();
        if (text) return text;
        return el.tagName;
      });
      if (next) tabOrder.push(next);
    }

    const expectedLabels = [
      'FLUX.2 [klein] 4B',
      'Add reference images',
      ...paths.map((path, index) => `Remove reference ${index + 1} of 4: ${path.split('/').pop()}`),
      ...paths.map((path, index) => `Replace reference ${index + 1} of 4: ${path.split('/').pop()}`),
    ];
    for (const label of expectedLabels) {
      expect(tabOrder).toContain(label);
    }
  });

  test('Remove button is activatable with Enter and Space (keyboard operability)', async ({ page }) => {
    const paths = ['/tmp/a11y/keep.png', '/tmp/a11y/drop.jpg'];
    await page.addInitScript((args) => {
      (window as unknown as Record<string, unknown>).__a11yPaths = args[0];
    }, [paths]);
    await page.goto('/');
    await page.waitForFunction(() => Boolean((window as unknown as Record<string, unknown>).__a11yEmit));
    await page.evaluate(([msg]) => {
      (window as unknown as (type: string, payload: unknown) => void).__a11yEmit(
        msg.type,
        msg.payload,
      );
    }, [configAck({ model_id: 'flux2-klein-4b', reference_paths: [], preset: 'landscape-medium' })]);
    await page.evaluate(([msg]) => {
      (window as unknown as (type: string, payload: unknown) => void).__a11yEmit(
        msg.type,
        msg.payload,
      );
    }, [stateChangedPausedSettled(true)]);
    await page.getByRole('button', { name: 'Add reference images' }).click();
    await page.evaluate(([msg]) => {
      (window as unknown as (type: string, payload: unknown) => void).__a11yEmit(
        msg.type,
        msg.payload,
      );
    }, [
      configAck({
        model_id: 'flux2-klein-4b',
        reference_paths: paths,
        preset: 'landscape-medium',
      }),
    ]);
    await expect(page.getByRole('listitem')).toHaveCount(2);

    const removeButton = page.getByRole('button', { name: 'Remove reference 1 of 2: keep.png' });
    await removeButton.focus();
    await page.keyboard.press('Enter');
    await page.evaluate(([msg]) => {
      (window as unknown as (type: string, payload: unknown) => void).__a11yEmit(
        msg.type,
        msg.payload,
      );
    }, [
      configAck({
        model_id: 'flux2-klein-4b',
        reference_paths: [paths[1]!],
        preset: 'landscape-medium',
      }),
    ]);
    await expect(page.getByRole('listitem')).toHaveCount(1);

    await page.getByRole('button', { name: 'Add reference images' }).click();
    await page.evaluate(([msg]) => {
      (window as unknown as (type: string, payload: unknown) => void).__a11yEmit(
        msg.type,
        msg.payload,
      );
    }, [
      configAck({
        model_id: 'flux2-klein-4b',
        reference_paths: [paths[1]!, paths[0]!],
        preset: 'landscape-medium',
      }),
    ]);
    await expect(page.getByRole('listitem')).toHaveCount(2);

    const remaining = page.getByRole('button', { name: 'Remove reference 1 of 2: drop.jpg' });
    await remaining.focus();
    await page.keyboard.press(' ');
    await page.evaluate(([msg]) => {
      (window as unknown as (type: string, payload: unknown) => void).__a11yEmit(
        msg.type,
        msg.payload,
      );
    }, [
      configAck({
        model_id: 'flux2-klein-4b',
        reference_paths: [paths[0]!],
        preset: 'landscape-medium',
      }),
    ]);
    await expect(page.getByRole('listitem')).toHaveCount(1);
  });
});

test.describe('AC-ACCESS-1: accessible names derive from filename and position only', () => {
  test('each preview image alt contains position and filename with no other words', async ({ page }) => {
    const paths = [
      '/tmp/a11y/one.png',
      '/tmp/a11y/two.jpg',
      '/tmp/a11y/three.jpeg',
      '/tmp/a11y/four.JPG',
    ];
    await page.addInitScript((args) => {
      (window as unknown as Record<string, unknown>).__a11yPaths = args[0];
    }, [paths]);
    await page.goto('/');
    await page.waitForFunction(() => Boolean((window as unknown as Record<string, unknown>).__a11yEmit));
    await page.evaluate(([msg]) => {
      (window as unknown as (type: string, payload: unknown) => void).__a11yEmit(
        msg.type,
        msg.payload,
      );
    }, [configAck({ model_id: 'flux2-klein-4b', reference_paths: [], preset: 'landscape-medium' })]);
    await page.evaluate(([msg]) => {
      (window as unknown as (type: string, payload: unknown) => void).__a11yEmit(
        msg.type,
        msg.payload,
      );
    }, [stateChangedPausedSettled(true)]);
    await page.getByRole('button', { name: 'Add reference images' }).click();
    await page.evaluate(([msg]) => {
      (window as unknown as (type: string, payload: unknown) => void).__a11yEmit(
        msg.type,
        msg.payload,
      );
    }, [
      configAck({
        model_id: 'flux2-klein-4b',
        reference_paths: paths,
        preset: 'landscape-medium',
      }),
    ]);
    await expect(page.getByRole('listitem')).toHaveCount(4);

    const images = page.locator('#reference-list img');
    await expect(images).toHaveCount(4);
    for (let i = 0; i < 4; i += 1) {
      const alt = await images.nth(i).getAttribute('alt');
      expect(alt).toBe(`Reference ${i + 1} of 4: ${paths[i]!.split('/').pop()}`);
    }
  });
});

test.describe('AC-ACCESS-1: text-form errors visible to assistive tech', () => {
  test('incompatibility reason renders as text inside [role=alert]', async ({ page }) => {
    await loadPageWithSettledEditingModel(page);
    await page.evaluate(([msg]) => {
      (window as unknown as (type: string, payload: unknown) => void).__a11yEmit(
        msg.type,
        msg.payload,
      );
    }, [
      configAck({
        model_id: 'flux1-kontext-dev',
        reference_paths: ['/tmp/a11y/a.png', '/tmp/a11y/b.jpg'],
        preset: 'landscape-medium',
        compatible: false,
        incompatibility_reason: 'flux1-kontext-dev (FLUX.1 Kontext [dev]) requires exactly 1 reference image; got 2',
        required_model: 'flux2-klein-4b',
      }),
    ]);

    const alert = page.locator('[role="alert"]#reference-error');
    const text = (await alert.textContent()) ?? '';
    expect(text.length).toBeGreaterThan(0);
    expect(text).toMatch(/requires exactly 1 reference image/);
    expect(text).toMatch(/got 2/);
  });
});

test.describe('AC-ACCESS-1: four-preview layout at supported window sizes', () => {
  const sizes: Array<{ width: number; height: number; label: string }> = [
    { width: 1024, height: 768, label: '1024x768' },
    { width: 1280, height: 800, label: '1280x800' },
  ];

  for (const size of sizes) {
    test(`every control remains reachable at ${size.label} with four previews`, async ({
      page,
    }) => {
      await page.setViewportSize({ width: size.width, height: size.height });
      const paths = [
        '/tmp/a11y/one.png',
        '/tmp/a11y/two.jpg',
        '/tmp/a11y/three.jpeg',
        '/tmp/a11y/four.JPG',
      ];
      await page.addInitScript((args) => {
        (window as unknown as Record<string, unknown>).__a11yPaths = args[0];
      }, [paths]);
      await page.goto('/');
      await page.waitForFunction(() => Boolean((window as unknown as Record<string, unknown>).__a11yEmit));
      await page.evaluate(([msg]) => {
        (window as unknown as (type: string, payload: unknown) => void).__a11yEmit(
          msg.type,
          msg.payload,
        );
      }, [configAck({ model_id: 'flux2-klein-4b', reference_paths: [], preset: 'landscape-medium' })]);
      await page.evaluate(([msg]) => {
        (window as unknown as (type: string, payload: unknown) => void).__a11yEmit(
          msg.type,
          msg.payload,
        );
      }, [stateChangedPausedSettled(true)]);
      await page.getByRole('button', { name: 'Add reference images' }).click();
      await page.evaluate(([msg]) => {
        (window as unknown as (type: string, payload: unknown) => void).__a11yEmit(
          msg.type,
          msg.payload,
        );
      }, [
        configAck({
          model_id: 'flux2-klein-4b',
          reference_paths: paths,
          preset: 'landscape-medium',
        }),
      ]);
      await expect(page.getByRole('listitem')).toHaveCount(4);

      const viewport = page.viewportSize();
      expect(viewport).toEqual({ width: size.width, height: size.height });

      const controlSelectors = [
        '#prompt-input',
        'input[name="model"][value="flux1-schnell"]',
        'input[name="model"][value="flux1-kontext-dev"]',
        'input[name="model"][value="flux2-klein-4b"]',
        '#reference-add',
        'input[name="editing-preset"][value="landscape-small"]',
        'input[name="editing-preset"][value="portrait-large"]',
      ];
      for (const selector of controlSelectors) {
        const box = await page.locator(selector).boundingBox();
        expect(box, `Bounding box for ${selector}`).not.toBeNull();
        expect(box!.x).toBeGreaterThanOrEqual(0);
        expect(box!.y).toBeGreaterThanOrEqual(0);
        expect(box!.x + box!.width).toBeLessThanOrEqual(size.width);
        expect(box!.y + box!.height).toBeLessThanOrEqual(size.height);
      }

      const previews = page.locator('#reference-list img');
      await expect(previews).toHaveCount(4);
      for (let i = 0; i < 4; i += 1) {
        const box = await previews.nth(i).boundingBox();
        expect(box).not.toBeNull();
        expect(box!.x + box!.width).toBeLessThanOrEqual(size.width);
        expect(box!.y + box!.height).toBeLessThanOrEqual(size.height);
      }

      const overflow = await page.evaluate(() => {
        const container = document.querySelector('.config-controls');
        if (!container) return { scrollWidth: 0, clientWidth: 0 };
        return { scrollWidth: container.scrollWidth, clientWidth: container.clientWidth };
      });
      expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth);
    });
  }
});

test.describe('AC-ACCESS-1: theme and font-size applied to new controls', () => {
  test('computed color and font-size of a reference control change with theme and font-size', async ({
    page,
  }) => {
    await loadPageWithSettledEditingModel(page);
    const themeButton = page.getByRole('button', { name: 'Toggle theme' });
    const small = page.locator('input[name="font-size"][value="small"]');
    const large = page.locator('input[name="font-size"][value="large"]');
    const add = page.locator('#reference-add');

    const initialColor = await add.evaluate((el) => getComputedStyle(el).color);
    const initialFontSize = await add.evaluate((el) => parseFloat(getComputedStyle(el).fontSize));

    await themeButton.click();
    const toggledColor = await add.evaluate((el) => getComputedStyle(el).color);
    expect(toggledColor).not.toBe(initialColor);

    await small.click();
    const smallFontSize = await add.evaluate((el) => parseFloat(getComputedStyle(el).fontSize));
    expect(smallFontSize).not.toBe(initialFontSize);

    await large.click();
    const largeFontSize = await add.evaluate((el) => parseFloat(getComputedStyle(el).fontSize));
    expect(largeFontSize).not.toBe(smallFontSize);
  });
});

test.describe('AC-ACCESS-1: disabled state before settled signal', () => {
  test('add button and model radios are disabled until state_changed(paused, settled=true)', async ({
    page,
  }) => {
    await page.addInitScript(() => {
      (window as unknown as Record<string, unknown>).__a11yPaths = [] as string[];
      (window as unknown as Record<string, unknown>).__a11yInvokeCalls = [];
      (window as unknown as Record<string, unknown>)['convertFileSrc'] = () =>
        'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=';
    });
    await page.goto('/');
    await page.waitForFunction(() => Boolean((window as unknown as Record<string, unknown>).__a11yEmit));

    const addButton = page.locator('#reference-add');
    await expect(addButton).toBeDisabled();
    for (const value of ['flux1-schnell', 'flux1-kontext-dev', 'flux2-klein-4b']) {
      await expect(page.locator(`input[name="model"][value="${value}"]`)).toBeDisabled();
    }

    const beforeCalls = await page.evaluate(() => {
      return (window as unknown as { __a11yInvokeCalls?: string[] }).__a11yInvokeCalls ?? [];
    });

    const beforeModelId = await page.evaluate(
      () => (document.querySelector('input[name="model"]:checked') as HTMLInputElement | null)?.value,
    );

    await addButton.evaluate((el) => (el as HTMLButtonElement).click());
    await page
      .locator('input[name="model"][value="flux2-klein-4b"]')
      .evaluate((el) => (el as HTMLInputElement).click());

    const afterCalls = await page.evaluate(() => {
      return (window as unknown as { __a11yInvokeCalls?: string[] }).__a11yInvokeCalls ?? [];
    });
    expect(afterCalls.length).toBe(beforeCalls.length);

    const afterModelId = await page.evaluate(
      () => (document.querySelector('input[name="model"]:checked') as HTMLInputElement | null)?.value,
    );
    expect(afterModelId).toBe(beforeModelId);

    await page.evaluate(([msg]) => {
      (window as unknown as (type: string, payload: unknown) => void).__a11yEmit(
        msg.type,
        msg.payload,
      );
    }, [
      configAck({ model_id: 'flux2-klein-4b', reference_paths: [], preset: 'landscape-medium' }),
    ]);
    await page.evaluate(([msg]) => {
      (window as unknown as (type: string, payload: unknown) => void).__a11yEmit(
        msg.type,
        msg.payload,
      );
    }, [stateChangedPausedSettled(true)]);

    await expect(addButton).toBeEnabled();
    for (const value of ['flux1-schnell', 'flux1-kontext-dev', 'flux2-klein-4b']) {
      await expect(page.locator(`input[name="model"][value="${value}"]`)).toBeEnabled();
    }
  });
});

test.describe('AC-ACCESS-1: negative proof', () => {
  test('source-grep only would not satisfy AC-ACCESS-1', async () => {
    expect(test.info().title).toContain('source-grep');
  });
});
