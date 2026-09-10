import {describe,it,expect} from 'vitest';
import {promises as fs} from 'node:fs';
import {execFileSync} from 'node:child_process';
import os from 'node:os';
import path from 'node:path';
import {IsolatedWorktree} from '../src/guardrails/worktree.js';
import {inside} from '../src/guardrails/paths.js';

describe('complete worktree review',()=>{
 it('includes new files, rejects stale reviews and applies without committing',async()=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'myai-review-test-'));
  const git=(...args:string[])=>execFileSync('git',args,{cwd:root,encoding:'utf8'}).trim();
  let work:IsolatedWorktree|undefined;
  try{
   git('init');git('config','user.email','test@example.test');git('config','user.name','Test');
   await fs.writeFile(path.join(root,'a.ts'),'export const a = 1;\n');git('add','a.ts');git('commit','-m','base');
   const before=git('rev-parse','HEAD');work=new IsolatedWorktree(root,'test');const folder=await work.create();
   await fs.writeFile(path.join(folder,'new.ts'),'export const b = 2;\n');
   expect(await work.diff()).toContain('+++ b/new.ts');
   await fs.writeFile(path.join(folder,'new.ts'),'export const b = 3;\n');
   await expect(work.applyReviewed()).rejects.toThrow('changed');
   await work.diff();await work.applyReviewed();
   expect(await fs.readFile(path.join(root,'new.ts'),'utf8')).toContain('3');
   expect(git('rev-parse','HEAD')).toBe(before);
   expect(git('diff','--cached','--name-only')).toBe('');
  }finally{if(work)await work.discard();await fs.rm(root,{recursive:true,force:true});}
 });
 it('rejects symbolic links and private planning paths',async()=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'myai-path-test-'));
  try{
   await expect(inside(root,'.local-planning/plan.md')).rejects.toThrow();
   await fs.symlink(os.tmpdir(),path.join(root,'link'));
   await expect(inside(root,'link/outside.ts')).rejects.toThrow('Symbolic');
  }finally{await fs.rm(root,{recursive:true,force:true});}
 });
});
