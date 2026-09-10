import { promises as fs } from 'node:fs';
import { execFileSync } from 'node:child_process';
import os from 'node:os';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { ProcessSandbox } from '../engine/sandbox.js';
import { inside } from './paths.js';

type Change = {name: string; before: Buffer | null; after: Buffer | null};
const hash = (changes: Change[]) => createHash('sha256').update(JSON.stringify(changes)).digest('hex');
const read = async (file: string): Promise<Buffer | null> => {
  try { return await fs.readFile(file); } catch(e) { if((e as NodeJS.ErrnoException).code === 'ENOENT')return null; throw e; }
};
export class IsolatedWorktree {
  public readonly branch: string;
  public path = '';
  private reviewed?: string;
  public constructor(private readonly repositoryRoot: string, taskId: string, private readonly sandbox = new ProcessSandbox()) {
    this.branch = `myai-feature/${taskId.replace(/[^a-zA-Z0-9._-]/g, '-')}`;
  }
  public async create(): Promise<string> {
    const parent = await fs.mkdtemp(path.join(os.tmpdir(), 'myai-worktree-'));
    this.path = path.join(parent, 'workspace');
    const result = await this.sandbox.run(['git','worktree','add','-b',this.branch,this.path,'HEAD'],{cwd:this.repositoryRoot,confirmed:true});
    if(result.exitCode!==0)throw new Error(result.stderr || 'Unable to create worktree.');
    return this.path;
  }
  public async discard(): Promise<void> {
    if(!this.path)return;
    const result=await this.sandbox.run(['git','worktree','remove','--force',this.path],{cwd:this.repositoryRoot,confirmed:true});
    if(result.exitCode!==0)throw new Error(result.stderr);
    await this.sandbox.run(['git','branch','-D',this.branch],{cwd:this.repositoryRoot,confirmed:true});
  }
  private async changes(): Promise<Change[]> {
    const git = (args: string[]) => execFileSync('git',args,{cwd:this.path,maxBuffer:16*1024*1024,stdio:['ignore','pipe','pipe']});
    const names = new Set([...git(['diff','--name-only','-z','HEAD']).toString().split('\0'), ...git(['ls-files','--others','--exclude-standard','-z']).toString().split('\0')].filter(Boolean));
    const result: Change[]=[];
    for(const name of [...names].sort()){
      const file=await inside(this.path,name);
      let before: Buffer|null=null;
      try{before=git(['show',`HEAD:${name}`]);}catch{/* new file */}
      const after=await read(file);
      if((before?.length || 0)>200_000 || (after?.length || 0)>200_000 || before?.includes(0) || after?.includes(0))throw new Error(`Review supports text files up to 200 KB: ${name}`);
      result.push({name,before,after});
    }
    return result;
  }
  public async diff(): Promise<string> {
    const changes=await this.changes();
    this.reviewed=hash(changes);
    // Full before/after review includes untracked additions and deletions.
    return changes.map(c=>`diff --git a/${c.name} b/${c.name}\n--- ${c.before===null?'/dev/null':'a/'+c.name}\n+++ ${c.after===null?'/dev/null':'b/'+c.name}\n`+
      (c.before?.toString().split('\n').map(l=>'-'+l).join('\n') || '')+'\n'+
      (c.after?.toString().split('\n').map(l=>'+'+l).join('\n') || '')+'\n').join('\n');
  }
  public async applyReviewed(): Promise<void> {
    const changes=await this.changes();
    if(!this.reviewed || hash(changes)!==this.reviewed)throw new Error('Working copy changed. View the latest diff before applying.');
    for(const c of changes){
      const current=await read(await inside(this.repositoryRoot,c.name));
      if(current===null ? c.before!==null : c.before===null || !current.equals(c.before))throw new Error(`Original changed: ${c.name}. Nothing applied.`);
    }
    const write=async(c: Change, key:'before'|'after')=>{
      const target=await inside(this.repositoryRoot,c.name);
      if(c[key]===null)await fs.unlink(target);
      else{await fs.mkdir(path.dirname(target),{recursive:true});await fs.writeFile(target,c[key]!);}
    };
    const written: Change[]=[];
    try{for(const c of changes){await write(c,'after');written.push(c);}}
    catch(error){for(const c of written.reverse())await write(c,'before');throw error;}
    // Keep the worktree as a recovery copy. No add, commit, merge or push.
  }
}
