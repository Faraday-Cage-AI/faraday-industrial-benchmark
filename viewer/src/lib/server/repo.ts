import path from 'node:path';

/** The viewer's own directory. `npm run dev` and `node build` both run from here. */
export const VIEWER_ROOT = process.cwd();

/** The benchmark repository that contains the viewer. */
export const REPO_ROOT = path.resolve(process.env.FARADAY_REPO ?? path.join(VIEWER_ROOT, '..'));
