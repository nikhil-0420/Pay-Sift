import {defineConfig} from 'vitest/config';
import react from '@vitejs/plugin-react';
export default defineConfig({
  plugins:[react()],
  server:{allowedHosts:['.manus.computer']},
  test:{environment:'node'},
  build:{rollupOptions:{output:{manualChunks:{react:['react','react-dom'],router:['react-router-dom'],query:['@tanstack/react-query','@tanstack/react-virtual'],motion:['framer-motion'],markdown:['react-markdown','dompurify']}}}}
});
